# Global Education Index ETL

This pipeline builds a clean master directory of UK universities. It pulls raw API data, converts unhashable Python lists into SQL-safe strings using lambda functions, drops records with missing website links, and removes duplicates before loading.

* **Extract:** `requests.get()`
* **Transform:** Lambda mapping, boolean filtering, `drop_duplicates()`
* **Load:** `sqlite3` (Behavior: `replace`)