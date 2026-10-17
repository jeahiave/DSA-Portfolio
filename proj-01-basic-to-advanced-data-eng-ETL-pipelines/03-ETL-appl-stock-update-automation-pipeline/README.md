# Stock Price Refresh and Chart

Fetches recent market history for a configurable ticker, validates and stores typed daily prices, prints a short summary calculated from the fetched values, and saves a chart. This pipeline does not generate AI text or require a model API key.

- **Source:** Yahoo Finance via `yfinance`.
- **Configuration:** `STOCK_TICKER`, `STOCK_PERIOD`, and `STOCK_INTERVAL`.
- **Validation:** OHLC price consistency, nonnegative volume, and latest-data age (`STOCK_MAX_STALENESS_DAYS`).
- **Destination:** `market_data` in `data/market_data.db`, or the configured `DATABASE_URL`.
- **Load behavior:** Transactional snapshot replacement for the configured date window.
- **Schema:** [`migrations/001_market_data.sql`](migrations/001_market_data.sql).
- **Output:** `promarketa_market_chart.png` alongside this script.
- **Run:** `scripts/run_pipeline.sh stock_update` from the repository root.

SQLite is the local default. Shared databases may use PostgreSQL; other dialects are rejected because the migration and conflict handling support SQLite and PostgreSQL. The summary describes recent price movement only and is not investment advice. The project uses a non-interactive plotting backend so it can run under cron.
