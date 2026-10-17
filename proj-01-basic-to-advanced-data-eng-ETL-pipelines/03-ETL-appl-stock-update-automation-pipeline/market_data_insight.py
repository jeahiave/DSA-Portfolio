"""Fetch recent prices, persist them, and produce a plain data summary and chart."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Headless backend for scheduled runs.
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_utils import apply_migrations, configure_logging, database_engine, load_frame, PipelineRun, validate_frame  # noqa: E402

TICKER = os.getenv("STOCK_TICKER", "AAPL").upper()
PERIOD = os.getenv("STOCK_PERIOD", "5d")
INTERVAL = os.getenv("STOCK_INTERVAL", "1d")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
MAX_STALENESS_DAYS = int(os.getenv("STOCK_MAX_STALENESS_DAYS", "7"))
logger = configure_logging("stock_update")


def transform(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        raise ValueError("Market data source returned no rows")
    frame = history.rename_axis("date").reset_index()
    frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
    frame = frame.rename(columns={"stock_splits": "stock_splits", "dividends": "dividends"})
    frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_localize(None)
    columns = ["date", "open", "high", "low", "close", "volume"]
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"Market data missing fields: {sorted(missing)}")
    frame = frame[columns].dropna(subset=columns).drop_duplicates(subset=["date"])
    frame["volume"] = frame["volume"].astype("int64")
    return frame


def validate_market_ranges(data: pd.DataFrame) -> None:
    valid_ohlc = (
        (data["low"] > 0)
        & (data["high"] >= data[["open", "close", "low"]].max(axis=1))
        & (data["low"] <= data[["open", "close", "high"]].min(axis=1))
        & (data["volume"] >= 0)
    )
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    latest_allowed = now + pd.Timedelta(days=1)
    source_is_stale = now - data["date"].max() > pd.Timedelta(days=MAX_STALENESS_DAYS)
    if not valid_ohlc.all() or (data["date"] > latest_allowed).any() or source_is_stale:
        raise ValueError("Stock OHLC, volume, or date values failed range checks")


def main() -> None:
    engine = database_engine("market_data")
    apply_migrations(engine, Path(__file__).parent / "migrations")
    with PipelineRun(engine, "stock_update", logger) as run:
        logger.info("Fetching market history", extra={"ticker": TICKER, "period": PERIOD,
                                                       "interval": INTERVAL})
        for attempt in range(1, 4):
            try:
                history = yf.Ticker(TICKER).history(
                    period=PERIOD, interval=INTERVAL, auto_adjust=False,
                    actions=False, timeout=TIMEOUT, raise_errors=True,
                )
                data = transform(history)
                break
            except Exception as error:
                if attempt == 3:
                    raise
                logger.warning("Market data request failed; retrying", extra={
                    "attempt": attempt, "max_attempts": 3, "error": str(error),
                })
                time.sleep(2 ** (attempt - 1))
        run.add_counts(fetched=len(history), filtered=len(history) - len(data))
        validate_frame(data, {"date": "datetime", "close": "numeric", "volume": "numeric"}, logger, {
            "date": "datetime", "open": "numeric", "high": "numeric",
            "low": "numeric", "close": "numeric", "volume": "numeric",
        })
        validate_market_ranges(data)

        # Prices are a refreshed snapshot for the configured window.
        run.add_counts(**load_frame(data, engine, "market_data", logger, conflict="replace"))
        ordered = data.sort_values("date")
        latest = ordered.iloc[-1]
        first_close = float(ordered.iloc[0]["close"])
        change_pct = (float(latest["close"]) / first_close - 1) * 100 if first_close else 0.0
        summary = (f"{TICKER} closed at ${latest['close']:.2f} on "
                   f"{latest['date']:%Y-%m-%d}, {change_pct:+.2f}% across "
                   f"{len(data)} trading sessions in this snapshot.")
        logger.info("Market summary", extra={"summary": summary})

        sns.set_theme(style="darkgrid")
        fig, axis = plt.subplots(figsize=(10, 6))
        sns.lineplot(data=data, x="date", y="close", marker="o", ax=axis,
                     color="#2E86AB", linewidth=2)
        axis.set(title=f"{TICKER} closing prices", xlabel="Trading date",
                 ylabel="Closing price (USD)")
        fig.autofmt_xdate()
        fig.tight_layout()
        chart_path = Path(__file__).parent / "promarketa_market_chart.png"
        fig.savefig(chart_path, dpi=180)
        plt.close(fig)
        logger.info("Chart saved", extra={"path": str(chart_path)})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Stock pipeline failed")
        raise
