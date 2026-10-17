"""Exit nonzero when any job has no recent successful run."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

import requests
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline_utils import configure_logging, database_engine  # noqa: E402

JOBS = {
    "employee_records": "employee_records",
    "global_education": "global_education",
    "global_earthquake": "earthquake_monitoring",
    "stock_update": "market_data",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-hours", type=float, default=30)
    args = parser.parse_args()
    logger = configure_logging("freshness_monitor")
    stale = []
    failed_jobs = []
    recent_failures = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for job, db_name in JOBS.items():
        engine = database_engine(db_name)
        try:
            with engine.connect() as connection:
                row = connection.execute(text(
                    "SELECT last_success, row_count FROM pipeline_runs WHERE job = :job"
                ), {"job": job}).first()
                latest_run = connection.execute(text(
                    "SELECT run_id, status, started_at, duration_seconds, error_message "
                    "FROM pipeline_run_events WHERE job = :job "
                    "ORDER BY started_at DESC LIMIT 1"
                ), {"job": job}).first()
        except Exception as error:
            logger.error("Freshness check unavailable", extra={"job": job, "error": str(error)})
            stale.append(job)
            continue
        if latest_run is not None and latest_run.status == "failed":
            failed_jobs.append(job)
            recent_failures.append({"job": job, "run_id": latest_run.run_id,
                                    "error": latest_run.error_message})
            logger.error("Most recent pipeline run failed", extra={
                "job": job, "run_id": latest_run.run_id,
                "duration_seconds": latest_run.duration_seconds,
                "error": latest_run.error_message,
            })
        if row is None:
            logger.error("No successful run recorded", extra={"job": job})
            stale.append(job)
            continue
        timestamp = row.last_success
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        age_hours = (now - timestamp).total_seconds() / 3600
        if age_hours > args.max_age_hours:
            logger.error("Pipeline data is stale", extra={"job": job, "age_hours": round(age_hours, 2)})
            stale.append(job)
        else:
            logger.info("Pipeline is fresh", extra={"job": job, "age_hours": round(age_hours, 2),
                                                      "row_count": row.row_count})
    if stale or failed_jobs:
        logger.error("Pipeline health check failed", extra={
            "stale_jobs": stale, "failed_jobs": failed_jobs,
        })
        webhook = os.getenv("ALERT_WEBHOOK_URL")
        if webhook:
            try:
                response = requests.post(
                    webhook,
                    json={"text": "ETL health check failed: " + ", ".join(
                              sorted(set(stale + failed_jobs))),
                          "stale_jobs": stale,
                          "failed_jobs": failed_jobs,
                          "recent_failures": recent_failures},
                    timeout=(3, 10),
                )
                response.raise_for_status()
                logger.info("Failure alert delivered", extra={
                    "stale_jobs": stale, "failed_jobs": failed_jobs,
                })
            except requests.RequestException:
                logger.exception("Could not deliver freshness alert")
        return 1
    logger.info("All pipelines are fresh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
