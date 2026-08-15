#%% 
#Importing necessary libraries
import sys
import requests
import pandas as pd
import numpy as np
import sqlite3 as sql


#%%
##Initiating Data Extraction from API

 # Defining API endpoint
url = "http://universities.hipolabs.com/search?country=United+Kingdom"  
try:
    response = requests.get(url)  # Making GET request to the API
    response.raise_for_status()  # Check if the request was successful
except requests.exceptions.ConnectionError as conn_err:
    print(f"Internet Connection Failed: {conn_err}")
    sys.exit()
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP Error Occurred: {http_err}")
    sys.exit()
except requests.exceptions.RequestException as req_err:
    print(f"Request Error Occurred: {req_err}")
    sys.exit()
except Exception as err:
    print(f"An Unexpected Error Occurred: {err}")
    sys.exit() 
    
raw_data = response.json()  # Parsing the JSON response
print("Data extraction successful!")
print(raw_data)


#%%
##Data Transformation
# Converting raw data to DataFrame
df = pd.json_normalize(raw_data)

# Cleaning column names by replacing dots with underscores
df.columns = df.columns.str.replace('.', '_')

# Convert list columns to comma-separated strings to make them hashable
for col in df.columns:
    df[col] = df[col].apply(lambda x: ', '.join(x) 
                            if isinstance(x, list) else x)
print("Data transformation successful!")

# Keep only the rows where web_pages is NOT EQUAL (!=) to an empty string
df = df[df['web_pages'] != ""]
print(f"\nShape after dropping empty websites: {df.shape}")

# Dropping duplicate rows from the DataFrame
df.drop_duplicates(inplace=True)
print(f"\nShape after dropping duplicates: {df.shape}")
print("Data cleaning successful!")
print(df)


# %%
##Connecting to the database
conn = sql.connect('global_education.db')
df.to_sql('universities', conn, if_exists='replace', index=False) # Loading clean datai nto the database
print("Data loading successful!")