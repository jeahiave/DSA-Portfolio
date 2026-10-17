import importlib.util
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


def load_script(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


employee = load_script("employee_pipeline", "00-ETL-daily-employee-record-data-pipeline/daily_employee_record.py")
education = load_script("education_pipeline", "01-ETL-global-education-data-pipeline/global_edu.py")
earthquake = load_script("earthquake_pipeline", "02-ETL-global-earthquake-data-pipeline/global_earthquake.py")
stock = load_script("stock_pipeline", "03-ETL-appl-stock-update-automation-pipeline/market_data_insight.py")


def test_employee_transform_flattens_expected_fields():
    frame = employee.transform([{
        "id": 7, "name": "Ada Example", "address": {"city": "Reykjavik", "geo": {"lat": "64", "lng": "-21"}},
        "company": {"name": "Example Co"},
    }])
    assert frame.loc[0, "employee_id"] == 7
    assert frame.loc[0, "address_geo_lat"] == 64
    assert frame.loc[0, "company_name"] == "Example Co"


def test_education_transform_filters_blank_sites_and_deduplicates():
    payload = [
        {"name": "University A", "country": "United Kingdom", "alpha_two_code": "GB",
         "web_pages": ["https://a.example"], "domains": ["a.example"]},
        {"name": "University A", "country": "United Kingdom", "alpha_two_code": "GB",
         "web_pages": ["https://a.example"], "domains": ["a.example"]},
        {"name": "No website", "country": "United Kingdom", "web_pages": [], "domains": []},
    ]
    frame = education.transform(payload)
    assert len(frame) == 1
    assert frame.loc[0, "web_pages"] == "https://a.example"


def test_earthquake_transform_filters_and_keys_events():
    payload = {"features": [
        {"id": "us1", "properties": {"mag": 4.2, "time": 100, "updated": 101},
         "geometry": {"type": "Point", "coordinates": [-120, 35, 5]}},
        {"id": "us2", "properties": {"mag": 2.9, "time": 100},
         "geometry": {"type": "Point", "coordinates": [-120, 35, 5]}},
        {"id": "us1", "properties": {"mag": 4.2, "time": 100},
         "geometry": {"type": "Point", "coordinates": [-120, 35, 5]}},
    ]}
    frame = earthquake.transform(payload, threshold=3.0)
    assert frame.event_id.tolist() == ["us1"]
    assert frame.loc[0, "depth_km"] == 5


def test_stock_transform_normalizes_market_history():
    index = pd.DatetimeIndex(["2025-01-02", "2025-01-03"], tz="America/New_York", name="Date")
    source = pd.DataFrame({
        "Open": [10.0, 11.0], "High": [12.0, 13.0], "Low": [9.0, 10.0],
        "Close": [11.0, 12.0], "Volume": [100, 120], "Dividends": [0, 0],
        "Stock Splits": [0, 0],
    }, index=index)
    result = stock.transform(source)
    assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert result.volume.tolist() == [100, 120]


def test_migration_and_load_are_repeatable_and_idempotent(monkeypatch):
    from pipeline_utils import apply_migrations, upsert_earthquakes

    engine = create_engine("sqlite:///:memory:")
    migrations = ROOT / "02-ETL-global-earthquake-data-pipeline" / "migrations"
    apply_migrations(engine, migrations)
    apply_migrations(engine, migrations)
    monkeypatch.setenv("APPLY_MIGRATIONS", "false")
    apply_migrations(engine, migrations)
    row = pd.DataFrame([{
        "event_id": "event-1", "magnitude": 4.0, "place": "Test",
        "event_time": 1, "updated_time": None, "longitude": 1.0,
        "latitude": 2.0, "depth_km": 3.0, "event_url": None,
        "source_type": "Point",
    }])
    import logging
    logger = logging.getLogger("test")
    assert upsert_earthquakes(row, engine, logger) == {"inserted": 1, "updated": 0, "skipped": 0}
    assert upsert_earthquakes(row, engine, logger) == {"inserted": 0, "updated": 0, "skipped": 1}
    revision = row.copy()
    revision.loc[0, "magnitude"] = 5.0
    revision.loc[0, "updated_time"] = 2
    assert upsert_earthquakes(revision, engine, logger) == {"inserted": 0, "updated": 1, "skipped": 0}
    older = revision.copy()
    older.loc[0, "magnitude"] = 6.0
    older.loc[0, "updated_time"] = 1
    assert upsert_earthquakes(older, engine, logger) == {"inserted": 0, "updated": 0, "skipped": 1}
    count = engine.connect().execute(text("SELECT COUNT(*) FROM weekly_earthquakes")).scalar_one()
    assert count == 1
    magnitude = engine.connect().execute(text(
        "SELECT magnitude FROM weekly_earthquakes WHERE event_id = 'event-1'"
    )).scalar_one()
    assert magnitude == 5.0


def test_each_project_migration_can_share_one_database():
    from pipeline_utils import apply_migrations

    engine = create_engine("sqlite:///:memory:")
    migration_dirs = [
        ROOT / name / "migrations"
        for name in (
            "00-ETL-daily-employee-record-data-pipeline",
            "01-ETL-global-education-data-pipeline",
            "02-ETL-global-earthquake-data-pipeline",
            "03-ETL-appl-stock-update-automation-pipeline",
        )
    ]
    for directory in migration_dirs:
        apply_migrations(engine, directory)
    with engine.connect() as connection:
        tables = set(connection.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )).scalars())
    assert {"employee_records", "universities", "weekly_earthquakes", "market_data",
            "pipeline_runs", "pipeline_run_events"} <= tables


def test_snapshot_load_replaces_previous_rows_transactionally():
    import logging
    from pipeline_utils import apply_migrations, load_frame

    engine = create_engine("sqlite:///:memory:")
    apply_migrations(engine, ROOT / "00-ETL-daily-employee-record-data-pipeline" / "migrations")
    first = employee.transform([{"id": 1, "name": "Old Name"}])
    second = employee.transform([{"id": 1, "name": "New Name"}])
    logger = logging.getLogger("test.snapshot")
    load_frame(first, engine, "employee_records", logger, conflict="replace")
    load_frame(second, engine, "employee_records", logger, conflict="replace")
    with engine.connect() as connection:
        values = connection.execute(text("SELECT full_name FROM employee_records")).scalars().all()
    assert values == ["New Name"]


def test_shared_schema_migration_upgrades_existing_run_database():
    from pipeline_utils import apply_migrations

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE schema_migrations "
            "(version VARCHAR(255) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        ))
        initial = ROOT / "migrations" / "000_pipeline_runs.sql"
        connection.execute(text(initial.read_text(encoding="utf-8")))
        connection.execute(text(
            "INSERT INTO schema_migrations (version) VALUES ('migrations/000_pipeline_runs.sql')"
        ))
        connection.execute(text(
            "INSERT INTO pipeline_runs (job, last_success, row_count) "
            "VALUES ('legacy_job', CURRENT_TIMESTAMP, 4)"
        ))
    apply_migrations(engine, ROOT / "02-ETL-global-earthquake-data-pipeline" / "migrations")
    with engine.connect() as connection:
        old_row = connection.execute(text(
            "SELECT row_count FROM pipeline_runs WHERE job='legacy_job'"
        )).scalar_one()
        event_table = connection.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_run_events'"
        )).scalar_one()
    assert old_row == 4
    assert event_table == "pipeline_run_events"


def test_pipeline_run_records_success_and_failure():
    import logging
    from pipeline_utils import PipelineRun, apply_migrations

    engine = create_engine("sqlite:///:memory:")
    apply_migrations(engine, ROOT / "02-ETL-global-earthquake-data-pipeline" / "migrations")
    logger = logging.getLogger("test.runs")
    with PipelineRun(engine, "sample", logger) as success:
        success.add_counts(fetched=5, filtered=2, inserted=2, skipped=1)
    with pytest.raises(RuntimeError, match="source unavailable"):
        with PipelineRun(engine, "sample", logger) as failure:
            failure.add_counts(fetched=1)
            raise RuntimeError("source unavailable")
    with engine.connect() as connection:
        success_row = connection.execute(text(
            "SELECT status, duration_seconds, fetched_count, inserted_count "
            "FROM pipeline_run_events WHERE run_id=:run_id"
        ), {"run_id": success.run_id}).one()
        failure_row = connection.execute(text(
            "SELECT status, error_message FROM pipeline_run_events WHERE run_id=:run_id"
        ), {"run_id": failure.run_id}).one()
        latest = connection.execute(text(
            "SELECT row_count FROM pipeline_runs WHERE job='sample'"
        )).scalar_one()
    assert success_row.status == "success"
    assert success_row.duration_seconds >= 0
    assert success_row.fetched_count == 5
    assert success_row.inserted_count == 2
    assert failure_row.status == "failed"
    assert failure_row.error_message == "source unavailable"
    assert latest == 2


def test_domain_range_validators_reject_invalid_locations_and_prices():
    from datetime import datetime

    bad_event = pd.DataFrame([{
        "longitude": 190.0, "latitude": 40.0, "depth_km": 3.0,
        "magnitude": 4.0, "event_time": 1, "updated_time": 2,
    }])
    with pytest.raises(ValueError, match="longitude"):
        earthquake.validate_event_ranges(bad_event)

    bad_prices = pd.DataFrame([{
        "date": datetime(2025, 1, 1), "open": 10.0, "high": 9.0,
        "low": 8.0, "close": 9.5, "volume": 100,
    }])
    with pytest.raises(ValueError, match="OHLC"):
        stock.validate_market_ranges(bad_prices)


def test_validate_frame_rejects_missing_required_values():
    from pipeline_utils import validate_frame

    with pytest.raises(ValueError, match="null"):
        validate_frame(pd.DataFrame({"id": [None]}), {"id": "numeric"},
                       __import__("logging").getLogger("test"))
