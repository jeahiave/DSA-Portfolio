##Importing necessary libraries
import sys
import requests
import sqlite3 as sql
import pandas as pd
import numpy as np

# Defining API endpoint
url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson"

# Fetching data from the API
try:
    response = requests.get(url)
    response.raise_for_status()  # Check if the request was successful
except requests.exceptions.ConnectionError as conn_err:
    print(f"Internet Connection failed: {conn_err}")
    sys.exit()
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred: {http_err}")
    sys.exit()
except Exception as err:
    print(f"An Unexpected error occurred: {err}")
    sys.exit()

# Parsing the JSON response
raw_data = response.json()
print("Earthquake data fetched successfully from the API.")

# Parsing the earthquake data and creating a DataFrame
global_earthquake_df = pd.json_normalize(raw_data['features'])

# Convert list columns (like geometry.coordinates) to strings so SQLite can store them
for col in global_earthquake_df.columns:
    global_earthquake_df[col] = global_earthquake_df[col].apply(lambda x: str(x) if isinstance(x, list) else x)

# Filtering earthquakes with magnitude above 3
quake_properties_above_3 = global_earthquake_df[global_earthquake_df['properties.mag'] > 3]

# Connecting to SQLite database and storing the earthquake data
conn = sql.connect('earthquake_monitoring.db')
quake_properties_above_3.to_sql('weekly_earthquakes', 
                                conn, if_exists='append', 
                                index=False)
conn.close()
print("Earthquake data has been successfully stored in the SQLite database.")