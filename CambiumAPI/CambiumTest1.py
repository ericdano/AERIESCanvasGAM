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
from sqlalchemy.engine import URL

"""
Test of the API to grab all the current users in Onboarding, including their passphrases and expiration dates. This is a read-only operation, so we use GET and not POST or PUT.

"""


def get_access_token(base_url, client_id, client_secret):
    token_url = f"{base_url}/api/v2/access/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    response = requests.post(token_url, data=payload, headers=headers, timeout=10)
    response.raise_for_status() 
    
    data = response.json()
    return data.get("access_token"), data.get("redirect_uri", base_url)

def get_all_paginated_users(base_url, client_id, client_secret, api_server_url, initial_token, portal_name):
    endpoint_url = f"{api_server_url}/api/v2/easypass/{portal_name}/onboarding/users"
    
    # We make token a variable we can update if it expires
    token = initial_token
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    all_users = []
    offset = 0
    limit = 100  
    
    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "managed_account": "Acalanes Union High School",
            "fields": "username,user_id,email,group,passphrase,expiration"
           }
        
        print(f"Fetching users {offset} to {offset + limit}...", flush=True)
        response = requests.get(endpoint_url, headers=headers, params=params, timeout=15)
        
        # --- Token Expiration Handler (401) ---
        if response.status_code == 401:
            print("\n--> Token expired! Re-authenticating on the fly...", flush=True)
            token, _ = get_access_token(base_url, client_id, client_secret)
            # Update the headers with the brand new token
            headers["Authorization"] = f"Bearer {token}"
            print("--> Resuming download...\n", flush=True)
            continue  # Retry the exact same offset with the new token
            
        # --- The Rate Limit Handler (429) ---
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            print(f"--> Rate limit hit! Pausing for {retry_after} seconds before retrying...", flush=True)
            time.sleep(retry_after)
            continue  
            
        # Catch any other weird errors
        response.raise_for_status()
        
        data = response.json()
        users_batch = data.get("data", [])
        
        if not users_batch:
            break
            
        all_users.extend(users_batch)
        
        total_users = data.get("paging", {}).get("total", 0)
        if offset + limit >= total_users:
            break
            
        offset += limit
        time.sleep(1.0) 
        
    return all_users

def store_users_in_db(df, db_connection_string):
    # Make sure dates are actual dates so SQL sees them correctly
    if 'expiration' in df.columns:
       df['expiration'] = pd.to_datetime(df['expiration'], errors='coerce')

    # We use create_engine here; we don't need the 'engine' module import
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": db_connection_string})
    sql_engine = create_engine(connection_url)
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
    aeries_local_conn_str = "DRIVER={SQL Server};SERVER=aerieslink.acalanes.k12.ca.us\LOCAL_AUHSD;DATABASE=" + configs['LocalAERIES_Cambium_DB'] + ";UID=" + configs['LocalAERIES_Username'] + ";PWD=" + configs['LocalAERIES_Password'] + ";"
    print("Starting batch download...", flush=True)
    thelogger.info('Cambium-User-Download ->Started')

    try:
        print("Authenticating...", flush=True)
        initial_token, api_server_url = get_access_token(BASE_URL, CLIENT_ID, CLIENT_SECRET)
        api_server_url = api_server_url.rstrip('/')
        
        print("\nStarting the pagination loop...", flush=True)
        
        # Notice we pass the credentials in now so it can renew itself!
        master_user_list = get_all_paginated_users(BASE_URL, CLIENT_ID, CLIENT_SECRET, api_server_url, initial_token, PORTAL_NAME)
        
        print(f"\n✅ Successfully downloaded {len(master_user_list)} users!")
        
        # --- Convert to Pandas ---
        df = pd.DataFrame(master_user_list)
        
        print("\n--- DataFrame Preview ---")
        print(df.head())
        
        # Save it to a CSV so you don't have to download it again!
        #df.to_csv("acalanes_students.csv", index=False)
        #print("\n💾 Saved all users to 'acalanes_students.csv' in your current directory.")
        store_users_in_db(df, aeries_local_conn_str)

    except Exception as err:
        print(f"\nAn error occurred: {err}", file=sys.stderr)
    end_of_timer = timer()
    thelogger.info('Cambium-User-Download ->Done!' + str(end_of_timer - start_of_timer))
    print("\nScript finished.", flush=True)
