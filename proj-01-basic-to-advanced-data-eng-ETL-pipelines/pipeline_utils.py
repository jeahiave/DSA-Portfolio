"""Shared utilities for the four standalone ETL examples."""
from __future__ import annotations

import logging
import json
import os
import time
import uuid
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.engine import Engine
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
load_dotenv(ROOT / ".env")
_run_id: ContextVar[str | None] = ContextVar("pipeline_run_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        standard = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "taskName",
        }
        data = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if _run_id.get():
            data["run_id"] = _run_id.get()
        data.update({key: value for key, value in record.__dict__.items()
                     if key not in standard and not key.startswith("_")})
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


def configure_logging(name: str) -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = JsonFormatter()
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        file_handler = RotatingFileHandler(
            LOG_DIR / f"{name}.log", maxBytes=5_000_000,
            backupCount=4, encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(stream)
        logger.addHandler(file_handler)
        logger.propagate = False
    return logger


def http_session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_json(url: str, logger: logging.Logger, timeout: float = 20) -> Any:
    logger.info("Fetching source", extra={"source_url": url})
    response = http_session().get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def validate_frame(
    frame: pd.DataFrame,
    required: dict[str, str],
    logger: logging.Logger,
    expected_types: dict[str, str] | None = None,
) -> None:
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Refusing to load an empty dataset")
    for column, expected in required.items():
        if frame[column].isna().any():
            raise ValueError(f"Required column {column!r} contains null values")
        if expected == "numeric" and not pd.api.types.is_numeric_dtype(frame[column]):
            raise TypeError(f"Column {column!r} must be numeric")
        if expected == "datetime" and not pd.api.types.is_datetime64_any_dtype(frame[column]):
            raise TypeError(f"Column {column!r} must contain datetimes")
        if expected == "text" and not frame[column].map(lambda x: isinstance(x, str)).all():
            raise TypeError(f"Column {column!r} must contain text values")
    for column, expected in (expected_types or {}).items():
        if column not in frame:
            raise ValueError(f"Expected typed column {column!r} is missing")
        values = frame[column].dropna()
        if expected == "numeric" and not pd.api.types.is_numeric_dtype(values):
            raise TypeError(f"Column {column!r} must be numeric")
        if expected == "text" and not values.map(lambda value: isinstance(value, str)).all():
            raise TypeError(f"Column {column!r} must contain text values")
        if expected == "datetime" and not pd.api.types.is_datetime64_any_dtype(frame[column]):
            raise TypeError(f"Column {column!r} must contain datetimes")
    logger.info("Validated rows", extra={"row_count": len(frame)})


def database_engine(name: str) -> Engine:
    configured = os.getenv("DATABASE_URL")
    if configured:
        url = make_url(configured)
        if url.get_backend_name() == "sqlite" and url.database not in (None, ":memory:"):
            db_path = Path(url.database)
            if not db_path.is_absolute():
                db_path = ROOT / db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(db_path))
        engine = create_engine(url, pool_pre_ping=True)
        if engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ValueError("DATABASE_URL must use SQLite or PostgreSQL")
        return engine
    db_path = ROOT / "data" / f"{name}.db"
    db_path.parent.mkdir(exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def apply_migrations(engine: Engine, migration_dir: Path, *, force: bool = False) -> None:
    """Apply ordered, one-file SQL migrations once per database."""
    migration_files = sorted((ROOT / "migrations").glob("*.sql"))
    migration_files.extend(sorted(migration_dir.glob("*.sql")))
    if not force and os.getenv("APPLY_MIGRATIONS", "true").lower() in {"0", "false", "no"}:
        expected = {str(path.relative_to(ROOT)) for path in migration_files}
        try:
            with engine.connect() as connection:
                applied = set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())
        except Exception as error:
            raise RuntimeError(
                "Migrations are disabled but schema_migrations is unavailable; "
                "run scripts/migrate.py with DDL-capable credentials first"
            ) from error
        missing = expected - applied
        if missing:
            raise RuntimeError(f"Migrations are disabled; pending migrations: {sorted(missing)}")
        return
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version VARCHAR(255) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        ))
        applied = set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())
        for migration in migration_files:
            version = str(migration.relative_to(ROOT))
            if version in applied:
                continue
            sql = migration.read_text(encoding="utf-8")
            for statement in (part.strip() for part in sql.split(";")):
                if statement:
                    connection.execute(text(statement))
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )
            applied.add(version)


def load_frame(
    frame: pd.DataFrame,
    engine: Engine,
    table: str,
    logger: logging.Logger,
    *,
    conflict: str = "append",
) -> dict[str, int]:
    """Insert into a migrated table; supports SQLite and PostgreSQL conflicts."""
    if conflict not in {"append", "ignore", "replace"}:
        raise ValueError(f"Unsupported conflict policy: {conflict}")
    if conflict == "ignore" and engine.dialect.name not in {"sqlite", "postgresql"}:
        raise ValueError("Idempotent inserts currently require SQLite or PostgreSQL")
    records = _db_records(frame)
    if not records:
        raise ValueError("Refusing to load an empty dataset")
    columns = list(frame.columns)
    quoted = ", ".join(f'"{column}"' for column in columns)
    binds = ", ".join(f":{column}" for column in columns)
    suffix = " ON CONFLICT DO NOTHING" if conflict == "ignore" else ""
    statement = text(f'INSERT INTO "{table}" ({quoted}) VALUES ({binds}){suffix}')
    with engine.begin() as connection:
        if conflict == "replace":
            connection.exec_driver_sql(f'DELETE FROM "{table}"')
        result = connection.execute(statement, records)
    inserted = len(records) if conflict in {"append", "replace"} else max(result.rowcount, 0)
    skipped = max(len(records) - inserted, 0)
    counts = {"inserted": inserted, "updated": 0, "skipped": skipped}
    logger.info("Loaded rows", extra={"table": table, **counts})
    return counts


def _db_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {key: (None if pd.isna(value) else
               value.to_pydatetime() if isinstance(value, pd.Timestamp)
               else value.item() if hasattr(value, "item") else value)
         for key, value in record.items()}
        for record in frame.to_dict(orient="records")
    ]


def upsert_earthquakes(frame: pd.DataFrame, engine: Engine, logger: logging.Logger) -> dict[str, int]:
    """Insert new USGS events and refresh existing rows only for newer revisions."""
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        raise ValueError("Earthquake upserts require SQLite or PostgreSQL")
    records = _db_records(frame)
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0}
    ids = [record["event_id"] for record in records]
    binds = {f"event_{index}": event_id for index, event_id in enumerate(ids)}
    slots = ", ".join(f":{key}" for key in binds)
    find_existing = text(
        f"SELECT event_id, updated_time FROM weekly_earthquakes WHERE event_id IN ({slots})"
    )
    columns = list(frame.columns)
    quoted = ", ".join(f'"{column}"' for column in columns)
    values = ", ".join(f":{column}" for column in columns)
    updates = ", ".join(
        f'"{column}" = excluded."{column}"'
        for column in columns if column != "event_id"
    )
    statement = text(
        f'INSERT INTO "weekly_earthquakes" ({quoted}) VALUES ({values}) '
        "ON CONFLICT (event_id) DO UPDATE SET " + updates + " "
        "WHERE excluded.updated_time IS NOT NULL AND "
        "(weekly_earthquakes.updated_time IS NULL OR "
        "excluded.updated_time > weekly_earthquakes.updated_time)"
    )
    with engine.begin() as connection:
        existing = {
            row.event_id: row.updated_time
            for row in connection.execute(find_existing, binds)
        }
        counts = {"inserted": 0, "updated": 0, "skipped": 0}
        for record in records:
            old_revision = existing.get(record["event_id"])
            new_revision = record["updated_time"]
            if record["event_id"] not in existing:
                counts["inserted"] += 1
            elif new_revision is not None and (
                old_revision is None or new_revision > old_revision
            ):
                counts["updated"] += 1
            else:
                counts["skipped"] += 1
            connection.execute(statement, record)
    logger.info("Upserted earthquake events", extra={"table": "weekly_earthquakes", **counts})
    return counts


class PipelineRun:
    """Capture one run's lifecycle, timing, and row counts in the database."""

    def __init__(self, engine: Engine, job: str, logger: logging.Logger):
        self.engine = engine
        self.job = job
        self.logger = logger
        self.run_id = str(uuid.uuid4())
        self.started = time.monotonic()
        self.counts = {
            "fetched": 0, "filtered": 0, "inserted": 0,
            "updated": 0, "skipped": 0,
        }
        self._context_token = None

    def __enter__(self) -> "PipelineRun":
        self._context_token = _run_id.set(self.run_id)
        try:
            with self.engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO pipeline_run_events "
                    "(run_id, job, started_at, status, fetched_count, filtered_count, "
                    "inserted_count, updated_count, skipped_count) "
                    "VALUES (:run_id, :job, CURRENT_TIMESTAMP, 'running', 0, 0, 0, 0, 0)"
                ), {"run_id": self.run_id, "job": self.job})
        except Exception:
            _run_id.reset(self._context_token)
            raise
        self.logger.info("Pipeline run started", extra={"job": self.job})
        return self

    def add_counts(self, **counts: int) -> None:
        for name, value in counts.items():
            if name not in self.counts:
                raise ValueError(f"Unknown run count: {name}")
            self.counts[name] += int(value)

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        duration = time.monotonic() - self.started
        status = "failed" if exc_type else "success"
        error = str(exc_value)[:2000] if exc_value else None
        values = {
            "run_id": self.run_id, "job": self.job, "status": status,
            "duration": duration, "error": error, **self.counts,
        }
        try:
            with self.engine.begin() as connection:
                connection.execute(text(
                    "UPDATE pipeline_run_events SET finished_at = CURRENT_TIMESTAMP, "
                    "status = :status, duration_seconds = :duration, "
                    "fetched_count = :fetched, filtered_count = :filtered, "
                    "inserted_count = :inserted, updated_count = :updated, "
                    "skipped_count = :skipped, error_message = :error "
                    "WHERE run_id = :run_id"
                ), values)
                if not exc_type:
                    connection.execute(text(
                        "INSERT INTO pipeline_runs (job, last_success, row_count) "
                        "VALUES (:job, CURRENT_TIMESTAMP, :row_count) "
                        "ON CONFLICT (job) DO UPDATE SET last_success = CURRENT_TIMESTAMP, "
                        "row_count = :row_count"
                    ), {"job": self.job,
                        "row_count": self.counts["inserted"] + self.counts["updated"]})
            final_fields = {
                "job": self.job, "status": status,
                "duration_seconds": round(duration, 3), **self.counts,
            }
            if error:
                final_fields["error"] = error
                self.logger.error("Pipeline run failed", extra=final_fields)
            else:
                self.logger.info("Pipeline run finished", extra=final_fields)
        finally:
            if self._context_token is not None:
                _run_id.reset(self._context_token)
        return False
