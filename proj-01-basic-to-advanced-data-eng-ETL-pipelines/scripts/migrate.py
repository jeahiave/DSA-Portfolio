"""Apply all pipeline migrations before scheduling jobs."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline_utils import apply_migrations, configure_logging, database_engine  # noqa: E402

PROJECTS = {
    "employee_records": "00-ETL-daily-employee-record-data-pipeline",
    "global_education": "01-ETL-global-education-data-pipeline",
    "earthquake_monitoring": "02-ETL-global-earthquake-data-pipeline",
    "market_data": "03-ETL-appl-stock-update-automation-pipeline",
}


def main() -> None:
    logger = configure_logging("migrations")
    for database, project in PROJECTS.items():
        engine = database_engine(database)
        apply_migrations(engine, ROOT / project / "migrations", force=True)
        logger.info("Project migrations are current", extra={"project": project})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        configure_logging("migrations").exception("Migration run failed")
        raise
