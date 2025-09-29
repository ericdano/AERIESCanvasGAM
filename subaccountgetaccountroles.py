import pandas as pd
import os, sys, shlex, subprocess, datetime, json, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

""" 
Python Script to get all Account Roles

2025 by Eric Dannewitz
"""
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

def main():
    start_of_timer = timer()
    WasThereAnError = False  
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
    Canvas_API_URL = configs['CanvasAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']  
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    # Need the main account to as we have to FIND the Term
    # This is in case multiple subaccounts want to do the same sort of thing
    account = canvas.get_account(1)

    # Miramonte HS is Subaccount 147
    subaccount = canvas.get_account(147)
    
    try:
        roles = account.get_roles()
        print(f"These are the roles found")
        for role in roles:
            print(f"{role.id} {role.label}  {role.is_account_role} {role.base_role_type} {role.role}")

    except Exception as e:
        print(f"An error occurred: {e}")
    try:
        roles = subaccount.get_roles()
        print(f"These are the roles found in subaccount")
        for role in roles:
            print(f"{role.id},{role.label},{role.is_account_role},{role.base_role_type},{role.role}")

    except Exception as e:
        print(f"An error occurred: {e}")

    role_id = get_role_id_by_label(subaccount,'Academy Teachers')
    users = subaccount.get_users(role_id=role_id)
    for user in users:
        print(f"{user.name} - {user.id}")
if __name__ == '__main__':
    main()