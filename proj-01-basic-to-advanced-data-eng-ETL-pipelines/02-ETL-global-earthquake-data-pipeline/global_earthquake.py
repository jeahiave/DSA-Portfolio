"""Load qualifying USGS events idempotently using the feed's event ID."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_utils import apply_migrations, configure_logging, database_engine, fetch_json, PipelineRun, upsert_earthquakes, validate_frame  # noqa: E402

MAGNITUDE_THRESHOLD = float(os.getenv("EARTHQUAKE_MAGNITUDE_THRESHOLD", "3.0"))
FEED = os.getenv("EARTHQUAKE_FEED", "all_week")
if FEED not in {"all_hour", "all_day", "all_week", "all_month"}:
    raise ValueError("EARTHQUAKE_FEED must be all_hour, all_day, all_week, or all_month")
URL = os.getenv("EARTHQUAKE_API_URL", f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{FEED}.geojson")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
logger = configure_logging("global_earthquake")


def transform(payload: dict, threshold: float = MAGNITUDE_THRESHOLD) -> pd.DataFrame:
    rows = []
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        magnitude = props.get("mag")
        event_id = feature.get("id")
        if not event_id or magnitude is None or float(magnitude) <= threshold or len(coords) < 3:
            continue
        longitude, latitude, depth = coords[:3]
        if any(value is None for value in (longitude, latitude, depth)):
            continue
        rows.append({
            "event_id": str(event_id), "magnitude": float(magnitude),
            "place": props.get("place"), "event_time": int(props["time"]),
            "updated_time": int(props["updated"]) if props.get("updated") is not None else None,
            "longitude": float(longitude), "latitude": float(latitude),
            "depth_km": float(depth), "event_url": props.get("url"),
            "source_type": geometry.get("type"),
        })
    return pd.DataFrame(rows, columns=[
        "event_id", "magnitude", "place", "event_time", "updated_time",
        "longitude", "latitude", "depth_km", "event_url", "source_type",
    ]).sort_values("updated_time", na_position="first").drop_duplicates(
        subset=["event_id"], keep="last").reset_index(drop=True)


def validate_event_ranges(data: pd.DataFrame) -> None:
    if data.empty:
        return
    if not data["longitude"].between(-180, 180).all():
        raise ValueError("Earthquake longitude must be between -180 and 180")
    if not data["latitude"].between(-90, 90).all():
        raise ValueError("Earthquake latitude must be between -90 and 90")
    if (data["depth_km"] < 0).any():
        raise ValueError("Earthquake depth cannot be negative")
    if not data["magnitude"].between(-2, 10).all():
        raise ValueError("Earthquake magnitude is outside the accepted range [-2, 10]")
    revisions = data["updated_time"].notna()
    if (data.loc[revisions, "updated_time"] < data.loc[revisions, "event_time"]).any():
        raise ValueError("Earthquake revision time cannot precede event time")


def main() -> None:
    engine = database_engine("earthquake_monitoring")
    apply_migrations(engine, Path(__file__).parent / "migrations")
    with PipelineRun(engine, "global_earthquake", logger) as run:
        payload = fetch_json(URL, logger, TIMEOUT)
        features = payload.get("features", [])
        data = transform(payload)
        run.add_counts(fetched=len(features), filtered=len(features) - len(data))
        if data.empty:
            logger.info("No events above configured threshold", extra={"threshold": MAGNITUDE_THRESHOLD})
            return
        validate_frame(data, {"event_id": "text", "magnitude": "numeric",
                              "longitude": "numeric", "latitude": "numeric"}, logger, {
            "event_id": "text", "magnitude": "numeric", "place": "text",
            "event_time": "numeric", "updated_time": "numeric", "longitude": "numeric",
            "latitude": "numeric", "depth_km": "numeric", "event_url": "text",
            "source_type": "text",
        })
        validate_event_ranges(data)
        run.add_counts(**upsert_earthquakes(data, engine, logger))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Earthquake pipeline failed")
        raise
