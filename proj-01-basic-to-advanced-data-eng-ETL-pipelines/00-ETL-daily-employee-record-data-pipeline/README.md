# Daily Employee Records ETL

Fetches the JSONPlaceholder mock user directory, flattens nested address and company fields, checks required values, and refreshes a typed SQL table.

- **Source:** `EMPLOYEE_API_URL` (defaults to JSONPlaceholder users).
- **Destination:** `employee_records` in the default `data/employee_records.db`, or the configured `DATABASE_URL`.
- **Load behavior:** Snapshot replacement in one transaction.
- **Schema:** [`migrations/001_employee_records.sql`](migrations/001_employee_records.sql).
- **Run:** `scripts/run_pipeline.sh employee_records` from the repository root.

The endpoint supplies sample data rather than actual staff records. Shared request timeouts, retries, JSON logs, schema migrations, and freshness tracking are implemented in the repository's `pipeline_utils.py`.
