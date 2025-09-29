import os
from canvasapi import Canvas
from canvasapi.exceptions import Unauthorized, InvalidAccessToken, ResourceDoesNotExist
import pandas as pd
import os, sys, shlex, subprocess, datetime, json, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from canvasapi.exceptions import CanvasException

# This script retrieves and lists all users with a specific role
# in a specific Canvas LMS subaccount.
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
    configs = json.load(f)
if configs['logserveraddress'] is None:
    logfilename = Path.home() / ".Acalanes" / configs['logfilename']
    thelogger = logging.getLogger('MyLogger')
    thelogger.basicConfig(filename=str(logfilename), level=thelogger.info)
else:
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
API_URL = configs['CanvasAPIURL']
API_KEY = configs['CanvasAPIKey']  
# Need the main account to as we have to FIND the Term
# This is in case multiple subaccounts want to do the same sort of thing
#    account = canvas.get_account(1)

# Miramonte HS is Subaccount 147
#    subaccount = canvas.get_account(147)
    

# The ID of the subaccount you want to query. You can find this in the URL
# of the subaccount's page in Canvas (e.g., .../accounts/<SUBACCOUNT_ID>).
SUBACCOUNT_ID = 147

# The label of the custom role you want to find.
TARGET_ROLE_LABEL = "Academy Teachers"

# --- Helper Function ---
def get_role_id_by_label(canvas_account, role_label):
    """
    Finds the ID of a role given its label within a Canvas account.

    Args:
        canvas_account (canvasapi.account.Account): The Canvas account object.
        role_label (str): The label of the role to find.

    Returns:
        int: The ID of the role, or None if not found.
    """
    try:
        # get_roles() returns a paginated list of Role objects
        roles = canvas_account.get_roles()
        for role in roles:
            if role.label == role_label:
                return role.id
    except Exception as e:
        print(f"Error fetching roles: {e}")
    return None

# --- Main Script ---
def get_users_with_role(api_url, api_key, subaccount_id, role_label):
    """
    Initializes the Canvas object and retrieves users with a specific role
    from a subaccount.

    Args:
        api_url (str): The base URL of the Canvas instance.
        api_key (str): The API access key.
        subaccount_id (int): The ID of the subaccount.
        role_label (str): The label of the role to filter by.

    Returns:
        list: A list of User objects, or None if an error occurs.
    """
    if not api_key or api_key == "<YOUR_API_KEY>":
        print("Error: API_KEY is not set. Please provide a valid API key.")
        return None

    try:
        # Initialize a new Canvas object
        print("Initializing Canvas API...")
        canvas = Canvas(api_url, api_key)

        # Get the subaccount object
        print(f"Retrieving subaccount with ID: {subaccount_id}...")
        subaccount = canvas.get_account(subaccount_id)
        
        # First, find the ID of the target role
        print(f"Finding role ID for '{role_label}'...")
        role_id = get_role_id_by_label(subaccount, role_label)

        if not role_id:
            print(f"Error: Role '{role_label}' not found in the subaccount.")
            return []

        # Get users from the subaccount, filtering by the found role ID
        print(f"Searching for users with role ID: {role_id}...")
        users = subaccount.get_users(role_id=role_id)

        return users

    except (Unauthorized, InvalidAccessToken):
        print("Error: Invalid API key or insufficient permissions.")
    except ResourceDoesNotExist:
        print(f"Error: Subaccount with ID {subaccount_id} does not exist.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    
    return None

if __name__ == "__main__":
    user_list = get_users_with_role(API_URL, API_KEY, SUBACCOUNT_ID, TARGET_ROLE_LABEL)

    if user_list is not None:
        if user_list:
            print(f"\nFound the following users with the role '{TARGET_ROLE_LABEL}':")
            for user in user_list:
                print(f"- {user.name} (ID: {user.id})")
        else:
            print(f"\nNo users found with the role '{TARGET_ROLE_LABEL}' in this subaccount.")
