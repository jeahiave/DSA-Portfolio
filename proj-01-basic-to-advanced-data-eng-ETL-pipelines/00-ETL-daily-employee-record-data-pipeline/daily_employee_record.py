#%%
# Importing necessary libraries
import sys
import requests
import pandas as pd
import sqlite3 as sql 


# %%
# Define the URL for the API endpoint
url = "https://jsonplaceholder.typicode.com/users"

## Extract the data from the API
try:
    response = requests.get(url)
    response.raise_for_status()
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred: {http_err}")
    sys.exit()
except requests.exceptions.ConnectionError as conn_err:
    print(f"Connection error occurred: {conn_err}")
    sys.exit()
except Exception as err:
    print(f"An unexpected error occurred: {err}")
    sys.exit()
    
raw_employee_data = response.json()
print(raw_employee_data)
print("Data fetched successfully from the API.")


#%%
#  Transform the JSON data to a pandas DataFrame
employee_records = pd.json_normalize(raw_employee_data)
employee_records

# Cleaning data
employee_records = employee_records.rename(columns={
    'id': 'employee_id',
    'name': 'full_name',
    'username': 'username',
    'email': 'email',
    'address.street': 'street',
    'address.suite': 'suite',
    'address.city': 'city',
    'address.zipcode': 'zipcode',
    'phone': 'phone',
    'website': 'website',
    'company.name': 'company_name'
})
employee_records
#%%
# This instantly changes "address.geo.lat" to "address_geo_lat"
employee_records.columns = employee_records.columns.str.replace('.', '_')

employee_records
# %%
# Connection to SQLite database
sql_conn = sql.connect('employee_records.db')
employee_records.to_sql("employee_records", 
                        sql_conn,
                        if_exists='replace', 
                        index=False)  
print("Data has been successfully stored in the SQLite database.") 
# %%
