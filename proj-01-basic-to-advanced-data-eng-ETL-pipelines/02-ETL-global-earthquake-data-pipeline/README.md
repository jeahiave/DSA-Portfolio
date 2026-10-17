# Global Earthquake Feed ETL

Reads a configurable USGS GeoJSON feed, selects events above the configured magnitude threshold, validates their identifying and location fields, and stores them as typed event records.

- **Source:** `EARTHQUAKE_FEED` (`all_hour`, `all_day`, `all_week`, or `all_month`); optionally override with `EARTHQUAKE_API_URL`.
- **Threshold:** `EARTHQUAKE_MAGNITUDE_THRESHOLD` (default `3.0`).
- **Destination:** `weekly_earthquakes` in `data/earthquake_monitoring.db`, or the configured `DATABASE_URL`.
- **Load behavior:** Append with `event_id` as the primary key; unchanged events are skipped and later USGS revisions update the stored row when `updated_time` increases.
- **Schema:** [`migrations/001_earthquakes.sql`](migrations/001_earthquakes.sql).
- **Run:** `scripts/run_pipeline.sh global_earthquake` from the repository root.

The selected feed is a rolling window, so repeats are expected. The event key makes reruns idempotent and keeps one stored row per USGS event. Coordinates, depth, revision timestamps, and magnitude are checked against valid ranges before loading. Each run records fetched, filtered, inserted, updated, and skipped counts. Shared request timeouts, retries, JSON logs, migrations, and freshness tracking are implemented in `pipeline_utils.py`.
