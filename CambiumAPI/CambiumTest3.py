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

def update_user_passphrase(api_server_url, token, portal_name, user_id, new_passphrase):
    """
    Sends a PUT request to update an existing user's credentials.
    """
    # Notice we append the specific user_id to the very end of the URL
    endpoint_url = f"{api_server_url}/api/v2/easypass/{portal_name}/onboarding/users/{user_id}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # We only send the fields we want to change, PLUS the required managed_account
    update_payload = {
        "passphrase": new_passphrase,
        "managed_account": "Acalanes Union High School"
    }
    
    # Using requests.put() for updating an existing resource
    response = requests.put(endpoint_url, headers=headers, json=update_payload, timeout=10)
    
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        print(f"\nHTTP error occurred: {http_err}", file=sys.stderr)
        if http_err.response is not None:
            print(f"Response Body: {http_err.response.text}", file=sys.stderr)
        sys.exit(1)
        
    # Cambium might return a 204 No Content for a successful update (meaning no JSON to return), 
    # so we handle that gracefully.
    if response.status_code == 204:
        return {"status": "success", "message": "Passphrase updated successfully (204 No Content)"}
        
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

    # Grab a user_id from your Pandas CSV export to test with!
    TARGET_USER_ID = "12345678" 
    NEW_PASSPHRASE = "GoDons2026!"

    print("Starting user update script...", flush=True)

    try:
        print("Authenticating...", flush=True)
        token, api_server_url = get_access_token(BASE_URL, CLIENT_ID, CLIENT_SECRET)
        api_server_url = api_server_url.rstrip('/')
        
        print(f"Updating passphrase for user_id '{TARGET_USER_ID}'...", flush=True)
        result = update_user_passphrase(api_server_url, token, PORTAL_NAME, TARGET_USER_ID, NEW_PASSPHRASE)
        
        print("\n✅ Successfully updated the user!")
        print("\n--- Server Response ---")
        print(result)
        
    except Exception as err:
        print(f"\nAn unexpected error occurred: {err}", file=sys.stderr)

    print("\nScript finished.", flush=True)