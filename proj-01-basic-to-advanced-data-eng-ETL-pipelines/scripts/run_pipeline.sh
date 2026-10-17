#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
JOB="${1:-}"
case "$JOB" in
  employee_records) SCRIPT="$ROOT/00-ETL-daily-employee-record-data-pipeline/daily_employee_record.py" ;;
  global_education) SCRIPT="$ROOT/01-ETL-global-education-data-pipeline/global_edu.py" ;;
  global_earthquake) SCRIPT="$ROOT/02-ETL-global-earthquake-data-pipeline/global_earthquake.py" ;;
  stock_update) SCRIPT="$ROOT/03-ETL-appl-stock-update-automation-pipeline/market_data_insight.py" ;;
  *) echo "Usage: $0 {employee_records|global_education|global_earthquake|stock_update}" >&2; exit 2 ;;
esac

if [[ ! -x "$PYTHON" ]]; then
  echo "Python executable not found: $PYTHON (set PYTHON or create the project venv)" >&2
  exit 2
fi
cd "$ROOT"
exec "$PYTHON" "$SCRIPT"
