# Daily Employee Roster ETL

This script extracts JSON employee data from a mock corporate API, flattens the nested structures, cleans dot-notation anomalies in the column headers, and loads a fresh snapshot into a local SQLite database (`employee_records.db`).

* **Extract:** `requests.get()`
* **Transform:** `pd.json_normalize()`
* **Load:** `sqlite3` (Behavior: `replace`)