"""Refresh a validated UK university reference directory."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_utils import apply_migrations, configure_logging, database_engine, fetch_json, load_frame, PipelineRun, validate_frame  # noqa: E402

COUNTRY = os.getenv("EDUCATION_COUNTRY", "United Kingdom")
URL = os.getenv("EDUCATION_API_URL", "https://universities.hipolabs.com/search?country=" + COUNTRY.replace(" ", "+"))
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
logger = configure_logging("global_education")


def transform(payload: list[dict]) -> pd.DataFrame:
    frame = pd.json_normalize(payload)
    if not {"name", "country", "web_pages"}.issubset(frame.columns):
        raise ValueError("University response is missing required fields")
    if frame["name"].isna().any() or frame["country"].isna().any():
        raise ValueError("University name and country are required")
    frame = frame[frame["name"].astype(str).str.strip().ne("")].copy()
    for column in ("web_pages", "domains"):
        if column not in frame:
            frame[column] = [[] for _ in range(len(frame))]
        frame[column] = frame[column].map(
            lambda value: ", ".join(map(str, value)) if isinstance(value, list)
            else ("" if pd.isna(value) else str(value))
        )
    frame = frame[frame.web_pages.str.strip().ne("")].copy()
    frame["alpha_two_code"] = frame.get("alpha_two_code", "")
    frame["state_province"] = frame.get("state-province")
    frame["university_id"] = frame.apply(
        lambda row: (str(row["alpha_two_code"]) + ":" + str(row["name"]).strip().casefold()
                     + ":" + row["web_pages"].casefold()), axis=1)
    return frame[["university_id", "name", "country", "alpha_two_code",
                  "state_province", "web_pages", "domains"]].drop_duplicates(
                      subset=["university_id"]).reset_index(drop=True)


def main() -> None:
    engine = database_engine("global_education")
    apply_migrations(engine, Path(__file__).parent / "migrations")
    with PipelineRun(engine, "global_education", logger) as run:
        payload = fetch_json(URL, logger, TIMEOUT)
        data = transform(payload)
        run.add_counts(fetched=len(payload), filtered=len(payload) - len(data))
        validate_frame(data, {"university_id": "text", "name": "text", "country": "text"}, logger, {
            "university_id": "text", "name": "text", "country": "text",
            "alpha_two_code": "text", "state_province": "text",
            "web_pages": "text", "domains": "text",
        })
        run.add_counts(**load_frame(data, engine, "universities", logger, conflict="replace"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Education pipeline failed")
        raise
