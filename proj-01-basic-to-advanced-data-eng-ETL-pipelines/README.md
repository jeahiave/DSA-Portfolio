# Four ETL Pipelines: A Practical Data Engineering Progression

This repository contains four small ETL projects, ordered from a first API-to-database workflow to a multi-step market data pipeline. They cover common data engineering work: fetching data, shaping and validating it, storing it with a defined schema, and making the result useful to another person or process.

These are learning projects, not production services. They now include shared configuration, retry and timeout handling, structured logs, SQL migrations, validation, repeatable loads, tests, and a freshness monitor so the examples also demonstrate the operational habits that make data jobs dependable.

## At a glance

| # | Project | Difficulty | Main practice | Database output |
|---|---|---|---|---|
| 1 | [Daily employee records](00-ETL-daily-employee-record-data-pipeline/) | Beginner | GET requests, nested JSON, basic cleaning, snapshot loading | `employee_records` |
| 2 | [Global education directory](01-ETL-global-education-data-pipeline/) | Beginner to intermediate | list conversion, filtering, stable keys, snapshot refresh | `universities` |
| 3 | [Global earthquake feed](02-ETL-global-earthquake-data-pipeline/) | Intermediate | GeoJSON, numeric thresholds, event keys, idempotent append | `weekly_earthquakes` |
| 4 | [Apple stock update](03-ETL-appl-stock-update-automation-pipeline/) | Intermediate to advanced | market data, database storage, computed summary, chart | `market_data` |

Difficulty reflects the number of concepts and integrations introduced. Project 4 is the broadest; project 3 introduces the key historical-data problem of repeat runs and duplicate events.

## The four projects

### 1. Daily employee records — beginner

[`daily_employee_record.py`](00-ETL-daily-employee-record-data-pipeline/daily_employee_record.py) fetches mock users from JSONPlaceholder, flattens address and company fields into columns, validates the employee identifier and name, and refreshes the `employee_records` table. A SQL migration defines the table and its column types.

This is a useful first ETL exercise because the source is simple and the full extract, transform, load cycle is visible in one script. In a workplace, the pattern resembles loading API records into a system that analysts can query. The sample records are mock data, not real employee information.

### 2. Global education directory — beginner to intermediate

[`global_edu.py`](01-ETL-global-education-data-pipeline/global_edu.py) fetches UK university records, joins list-valued website and domain fields into text, removes records without a website, assigns a stable directory key, and refreshes the `universities` table.

This adds practical data quality work: source fields are not always ready for a relational table, and a usable reference dataset needs consistent values and duplicate handling. The snapshot is replaced on each successful load.

### 3. Global earthquake feed — intermediate

[`global_earthquake.py`](02-ETL-global-earthquake-data-pipeline/global_earthquake.py) reads a configurable USGS GeoJSON feed, selects events above a magnitude threshold, validates coordinates and required values, and upserts events using the USGS event ID as the primary key. Repeated runs skip unchanged events and update a stored event only when USGS supplies a newer `updated_time` revision.

This project introduces event data and idempotency: a job may run more than once over the same time window, so the database needs a stable key and a duplicate policy. Event timestamps and coordinates are retained as typed columns for later analysis.

### 4. Apple stock update — intermediate to advanced

[`market_data_insight.py`](03-ETL-appl-stock-update-automation-pipeline/market_data_insight.py) retrieves a configurable recent period of Apple stock history through `yfinance`, validates and stores typed price fields, prints a short summary calculated directly from the data, and saves a chart. There is no AI text generation or model API dependency.

This combines source access, database work, and a clear analytical output. The price table is a refreshed snapshot for the selected window. The summary describes that data only; it is not investment guidance.

## How they build a foundation for data engineering

Together the scripts give practice in:

- Consuming HTTP APIs and handling nested JSON and GeoJSON.
- Turning source-specific fields into a consistent relational shape.
- Applying required-field, type, and business-rule checks before loading.
- Choosing snapshot replacement or append behavior based on how the data is used.
- Using primary keys and idempotent writes to make repeated runs safe.
- Defining explicit database types and tracking schema migrations.
- Producing data for downstream queries, charts, and operational monitoring.
- Thinking about failure handling, configuration, logs, scheduling, and freshness.

Those skills map to everyday work in ingestion jobs, reference data refreshes, event pipelines, and reporting. The projects are a starting point: a larger production system would also need service-specific access controls, alert delivery, richer data contracts, deployment management, and an agreed recovery process.

## Configuration

Copy `.env.example` to `.env` and edit values as needed. The scripts load that file from the repository root. The default database location is one SQLite file per pipeline under `data/`. To use a shared long-lived database, set `DATABASE_URL` to a SQLite or PostgreSQL SQLAlchemy URL; other database dialects are rejected because the migration and conflict handling are written for those two.

Configuration includes:

| Variable | Default | Used by |
|---|---|---|
| `REQUEST_TIMEOUT_SECONDS` | `20` | API jobs |
| `APPLY_MIGRATIONS` | `true` | Apply migrations at job startup; set `false` after a release migration step |
| `EMPLOYEE_API_URL` | JSONPlaceholder users endpoint | Employee pipeline |
| `EDUCATION_COUNTRY` | `United Kingdom` | Education pipeline |
| `EDUCATION_API_URL` | Hipolabs UK search endpoint | Education pipeline |
| `EARTHQUAKE_FEED` | `all_week` | Earthquake pipeline (`all_hour`, `all_day`, `all_week`, `all_month`) |
| `EARTHQUAKE_API_URL` | Derived from feed | Optional earthquake endpoint override |
| `EARTHQUAKE_MAGNITUDE_THRESHOLD` | `3.0` | Earthquake pipeline |
| `STOCK_TICKER` | `AAPL` | Stock pipeline |
| `STOCK_PERIOD` | `5d` | Stock pipeline, as supported by `yfinance` |
| `STOCK_INTERVAL` | `1d` | Stock pipeline, as supported by `yfinance` |
| `STOCK_MAX_STALENESS_DAYS` | `7` | Reject stock data whose latest date is too old |

The shared request client retries transient HTTP failures with backoff and honors `Retry-After`. Market history uses its own bounded retry loop. Logs go to the console and `logs/` as JSON, with a run ID attached while a job is active. Never commit `.env` or credentials.

## Setup and run

Use Python 3.10 or newer. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Run any job through the wrapper, which sets the repository as the working directory:

```bash
scripts/run_pipeline.sh employee_records
scripts/run_pipeline.sh global_education
scripts/run_pipeline.sh global_earthquake
scripts/run_pipeline.sh stock_update
```

The scripts also run directly with the configured Python environment. They create the database tables by applying SQL files under the shared `migrations/` folder and each project's `migrations/` folder. Applied migrations are recorded in `schema_migrations`; treat applied files as immutable and add a new numbered migration for schema changes. For a deployment that separates permissions, run `.venv/bin/python scripts/migrate.py` once with DDL-capable credentials, then set `APPLY_MIGRATIONS=false` for the scheduled jobs. The jobs verify that required migration versions are present before running.

## Repeat runs and data freshness

The employee, education, and stock tables are refreshed snapshots. The earthquake job appends qualifying events, skips unchanged IDs, and updates an existing row only when the incoming event revision is newer.

Each run records its status, run ID, duration, error (if any), and fetched, filtered, inserted, updated, and skipped counts in `pipeline_run_events`. Successful runs also update the latest-success marker in `pipeline_runs`. Run the monitor to fail if any job has not completed within the expected window:

```bash
.venv/bin/python scripts/check_freshness.py --max-age-hours 30
```

It returns status code 1 if a run is missing, stale, failed most recently, or its database cannot be checked, making it suitable for cron or a monitoring system. If `ALERT_WEBHOOK_URL` is configured, a JSON alert is sent on those conditions. The URL may contain a secret, so keep it in the ignored `.env` file locally or inject it from a managed secret store in a deployed environment. JSON log files rotate at 5 MB and retain four backups. Connect the monitor exit code to host alerting for delivery retries and escalation.

## Scheduling

[`cron_schedule.txt`](cron_schedule.txt) contains daily schedules using this repository's current absolute path and `.venv`. If you move the checkout or use another account, replace that path with the actual checkout location before installing the entries with `crontab -e`. All four jobs and the freshness check run daily. The monitor is scheduled after the jobs and checks all four within 30 hours.

The runner writes rotating job logs under `logs/`; cron captures runner-level errors in its own mail/output depending on the host configuration. Keep `ALERT_WEBHOOK_URL` empty for local use or configure a webhook that accepts the JSON payload for notifications.

## Database schema and migrations

Each pipeline has an initial SQL migration with explicit types and primary keys. Shared migrations create the latest-success and per-run history tables. The migration runner tracks applied files by repository-relative path, so identically named migration files in separate project folders do not collide when the jobs share a database. SQLite is the zero-setup default; PostgreSQL is supported for a shared database. Set `DATABASE_URL` accordingly, for example `postgresql+psycopg://user:password@host:5432/database`.

Back up a database before applying schema changes. For a local SQLite file, use SQLite's online backup command: `sqlite3 data/earthquake_monitoring.db ".backup 'earthquake_monitoring.backup.db'"`. For PostgreSQL, provide a standard PostgreSQL connection URI as `PGURI` and run `pg_dump "$PGURI" > before-migration.sql`. Store backups outside the repository and verify that they can be restored.

For a hosted deployment, provide database credentials through the platform's secret manager and separate the DDL-capable migration role from a runtime role with only the necessary read/write permissions. The migration command supports a release step before starting DML-only job credentials. The `.env` file is intended for local development; `.gitignore` excludes it.

## Tests

The pytest suite checks transformations, domain ranges, migration repeatability and upgrade behavior, run-history recording, and earthquake insert/update/skip behavior. It does not call external APIs. GitHub Actions runs the suite on Python 3.10, 3.12, and 3.13, with a syntax-focused lint check.

```bash
.venv/bin/python -m pytest
```

## Repository layout

```text
.
├── 00-ETL-daily-employee-record-data-pipeline/  # mock employee snapshot
├── 01-ETL-global-education-data-pipeline/       # university directory
├── 02-ETL-global-earthquake-data-pipeline/      # idempotent event feed
├── 03-ETL-appl-stock-update-automation-pipeline/ # market prices and chart
├── migrations/                                   # shared operational schema
├── pipeline_utils.py                            # shared HTTP, logs, DB helpers
├── scripts/                                     # runner and freshness check
├── tests/                                       # offline transformation/load tests
├── cron_schedule.txt
├── .env.example
└── requirements.txt
```
