import requests, logging, json
import sys
import time
from pathlib import Path
import pandas as pd
from timeit import default_timer as timer
from logging.handlers import SysLogHandler
from datetime import datetime

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

def add_onboarding_user(api_server_url, token, portal_name, new_user_data):
    """
    Sends a POST request to Cambium to create a new EasyPass Onboarding user.
    """
    endpoint_url = f"{api_server_url}/api/v2/easypass/{portal_name}/onboarding/users"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Notice we removed the 'params' dictionary completely!
    
    # We pass only the headers and the json payload
    response = requests.post(endpoint_url, headers=headers, json=new_user_data, timeout=10)
    
    # If there is another validation error with the payload itself, this will catch it
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        print(f"\nHTTP error occurred: {http_err}", file=sys.stderr)
        if http_err.response is not None:
            print(f"Response Body: {http_err.response.text}", file=sys.stderr)
        sys.exit(1) # Stop the script so we can read the error
        
    return response.json()

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
    # --- The Student Payload ---
    # Customize these fields. If you leave out 'passphrase', Cambium will usually auto-generate 
    # a secure ePSK for you automatically depending on your portal settings.
    new_student = {
        "username": "John Doe",
        "user_id": "12345678",
        "email": "jdoe@acalanes.k12.ca.us",
        "passphrase": "RubyRed99f",
        "device_limit": 2,
        "managed_account": "Acalanes Union High School",
        "expire": False
        #"group": "Class of 2026"  Optional: Great for filtering later!
    }

    print("Starting user creation script...", flush=True)

    try:
        print("Authenticating...", flush=True)
        token, api_server_url = get_access_token(BASE_URL, CLIENT_ID, CLIENT_SECRET)
        api_server_url = api_server_url.rstrip('/')
        
        print(f"Adding user '{new_student['email']}' to portal '{PORTAL_NAME}'...", flush=True)
        result = add_onboarding_user(api_server_url, token, PORTAL_NAME, new_student)
        
        print("\n✅ Successfully added the user!")
        print("\n--- Server Response ---")
        print(result) # This will usually print out the user_id and generated passphrase
        
    except requests.exceptions.HTTPError as http_err:
        print(f"\nHTTP error occurred: {http_err}", file=sys.stderr)
        if http_err.response is not None:
            print(f"Response Body: {http_err.response.text}", file=sys.stderr)
    except Exception as err:
        print(f"\nAn unexpected error occurred: {err}", file=sys.stderr)

    print("\nScript finished.", flush=True)