# Global Education Directory ETL

Fetches university listings for the configured country, converts website and domain lists to text, removes entries without a website, assigns a stable directory key, and refreshes the database snapshot.

- **Source:** `EDUCATION_API_URL` (defaults to the Hipolabs UK query); `EDUCATION_COUNTRY` controls the default query.
- **Destination:** `universities` in `data/global_education.db`, or the configured `DATABASE_URL`.
- **Load behavior:** Transactional snapshot replacement.
- **Schema:** [`migrations/001_universities.sql`](migrations/001_universities.sql).
- **Run:** `scripts/run_pipeline.sh global_education` from the repository root.

The stable key is derived from the country code, name, and website list. This makes repeated loads consistent and removes exact duplicate listings in a response. Shared request timeouts, retries, JSON logs, migrations, and freshness tracking are provided by `pipeline_utils.py`.
