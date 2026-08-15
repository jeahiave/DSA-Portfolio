# Data Engineering ETL Pipelines

# Live Global Earthquake Monitor

This advanced pipeline connects to the US Geological Survey (USGS) live GeoJSON feed. It targets and flattens specific nested arrays, drops missing coordinate data, and filters for earthquakes with a magnitude > 3.0 before appending the new records to a rolling historical database.

* **Extract:** USGS GeoJSON REST API
* **Transform:** Deep JSON targeting, Pandas boolean masking, array-to-string conversions
* **Load:** `sqlite3` (Behavior: `append`)