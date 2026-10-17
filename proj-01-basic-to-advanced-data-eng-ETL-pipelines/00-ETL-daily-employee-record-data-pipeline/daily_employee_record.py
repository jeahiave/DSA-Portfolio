"""Fetch, validate, and refresh the mock employee directory snapshot."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_utils import apply_migrations, configure_logging, database_engine, fetch_json, load_frame, PipelineRun, validate_frame  # noqa: E402

URL = os.getenv("EMPLOYEE_API_URL", "https://jsonplaceholder.typicode.com/users")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
logger = configure_logging("employee_records")


def transform(payload: list[dict]) -> pd.DataFrame:
    frame = pd.json_normalize(payload).rename(columns={
        "id": "employee_id", "name": "full_name", "address.street": "street",
        "address.suite": "suite", "address.city": "city",
        "address.zipcode": "zipcode", "company.name": "company_name",
        "address.geo.lat": "address_geo_lat", "address.geo.lng": "address_geo_lng",
    })
    columns = ["employee_id", "full_name", "username", "email", "street", "suite",
               "city", "zipcode", "phone", "website", "company_name",
               "address_geo_lat", "address_geo_lng"]
    for column in columns:
        if column not in frame:
            frame[column] = None
    for column in ("address_geo_lat", "address_geo_lng"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame[columns]


def main() -> None:
    engine = database_engine("employee_records")
    apply_migrations(engine, Path(__file__).parent / "migrations")
    with PipelineRun(engine, "employee_records", logger) as run:
        payload = fetch_json(URL, logger, TIMEOUT)
        data = transform(payload)
        run.add_counts(fetched=len(payload), filtered=len(payload) - len(data))
        validate_frame(data, {"employee_id": "numeric", "full_name": "text"}, logger, {
            "employee_id": "numeric", "full_name": "text", "username": "text",
            "email": "text", "street": "text", "suite": "text", "city": "text",
            "zipcode": "text", "phone": "text", "website": "text",
            "company_name": "text", "address_geo_lat": "numeric", "address_geo_lng": "numeric",
        })
        if (data["employee_id"] <= 0).any() or data["full_name"].str.strip().eq("").any():
            raise ValueError("Employee identifiers must be positive and names cannot be blank")
        if not data["address_geo_lat"].dropna().between(-90, 90).all():
            raise ValueError("Employee latitude must be between -90 and 90")
        if not data["address_geo_lng"].dropna().between(-180, 180).all():
            raise ValueError("Employee longitude must be between -180 and 180")
        run.add_counts(**load_frame(data, engine, "employee_records", logger, conflict="replace"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Employee pipeline failed")
        raise
