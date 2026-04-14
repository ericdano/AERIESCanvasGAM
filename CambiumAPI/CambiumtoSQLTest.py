import requests, logging, json
import sys
import time
from pathlib import Path
import pandas as pd
from timeit import default_timer as timer
from logging.handlers import SysLogHandler
from datetime import datetime
import urllib
from sqlalchemy import create_engine

def store_users_in_db(df, db_connection_string):
   # Make sure dates are actual dates so SQL sees them correctly
   if 'expiration' in df.columns:
       df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')

   quoted_conn_str = urllib.parse.quote_plus(db_connection_string)
   # We use create_engine here; we don't need the 'engine' module import
   sql_engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quoted_conn_str}")
   
   try:
       df.to_sql('Current_Passwords', con=sql_engine, if_exists='replace', index=False, method='multi')
       print("\n✅ Users stored in the database successfully!")
   except Exception as e:
       print(f"\n❌ Error occurred while storing users in the database: {e}")

if __name__ == '__main__':
    # --- Configuration ---
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)

    CLIENT_ID = configs['CambiumAPI_ClientID']
    CLIENT_SECRET = configs['CambiumAPI_ClientSecret']
    PORTAL_NAME = configs['CambiumAPI_PortalName']
    BASE_URL = configs['CambiumAPI_URL']
    print(confighome)
    # Build the connection string using SQL Server Authentication
    data = {
    'username': ['jsmith', 'adoe'],
    'user_id': [1001, 1002],
    'email': ['jsmith@school.edu', 'adoe@school.edu'],
    'passphrase': ['hashed_pwd_A', 'hashed_pwd_B'],
    'device_limit': [1, 2],
    'managed_account': [True, False], 
    'expire': [False, False]          
    }
    df= pd.DataFrame(data)
    # Replace PORT_NUMBER with the exact number you found in Configuration Manager
    server_name = r'AERIESLINK.acalanes.k12.ca.us,30000' 

    db_name = configs['LocalAERIES_Cambium_DB']
    uid = configs['LocalAERIES_Username']
    pwd = configs['LocalAERIES_Password']

    # The connection string using the direct port
    aeries_local_conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};"
    store_users_in_db(df, aeries_local_conn_str)