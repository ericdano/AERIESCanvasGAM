import pandas as pd
import json
import logging
import logging.handlers
import smtplib
import datetime
import socket
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage

"""
Script to suspend Canvas accounts for Graduated Seniors
2026
"""

def getConfigs():
    # Function to get passwords and API keys for Acalanes Canvas and stuff
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    return configs


def main():
    msgbody = ""
    configs = getConfigs()
    
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address=(configs['logserveraddress'], 514))
    thelogger.addHandler(handler)
    
    Canvas_API_URL = configs['CanvasAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']  
    canvas = Canvas(Canvas_API_URL, Canvas_API_KEY)

    account = canvas.get_account(1)

    target_suffix = "26@auhsdschools.org"
    print(f"Fetching users... (Optimized for speed)")

    users = account.get_users(include=['email'], per_page=100)

    matched_data = []

    for user in users:
        email = (getattr(user, 'email', '') or '').lower()
        login_id = (getattr(user, 'login_id', '') or '').lower()

        if email.endswith(target_suffix) or login_id.endswith(target_suffix):
            matched_data.append({
                'Canvas ID': user.id,
                'Name': user.name,
                'Email': email,
                'Login ID': login_id
            })

    df = pd.DataFrame(matched_data)

    print("\n--- Search Complete ---")
    if not df.empty:
        print(f"Found {len(df)} matching users.\n")
        print(df.head()) 
    else:
        print("No matches found. Exiting.")
        return 

    for index, row in df.iterrows():
        user_email = row['Email']
        canvas_id = row['Canvas ID']
        
        if pd.notna(user_email) and user_email != '':
            try:
                user = canvas.get_user(canvas_id)
                try:  
                    # 1. Send the suspension command
                    user.edit(user={'event': 'suspend'})
                    
                    # 2. VERIFICATION STEP: Fetch the logins and check the state
                    logins = user.get_user_logins() # <-- FIXED METHOD
                    is_suspended = False
                    
                    for login in logins:
                        if getattr(login, 'workflow_state', '') == 'suspended':
                            is_suspended = True
                            break 
                    
                    # 3. Log based on the verification result
                    if is_suspended:
                        log_msg = f"Verified: Disabled Canvas for -> {user_email}"
                        msgbody += f"✅ {log_msg}\n"
                        thelogger.info(f"ExpireADAccounts->{log_msg}")
                    else:
                        log_msg = f"Warning: API succeeded, but login not suspended for -> {user_email}"
                        msgbody += f"⚠️ {log_msg}\n"
                        thelogger.warning(f"ExpireADAccounts->{log_msg}")
                        
                except CanvasException as g:
                    log_msg = f"Error Disabling with Canvas -> {user_email} {g}"
                    msgbody += f"❌ {log_msg}\n"
                    thelogger.error(f"ExpireADAccounts->{log_msg}")
            except CanvasException as e:
                log_msg = f"Error fetching user from Canvas -> {user_email} {e}"
                msgbody += f"❌ {log_msg}\n"
                thelogger.error(f"ExpireADAccounts->{log_msg}")
                
    # Prepare Status Email
    msg = EmailMessage()
    msg['Subject'] = f"{configs.get('SMTPStatusMessage', 'Canvas Status')} Suspend Graduated Seniors Script {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['SendInfoEmailAddr']
    
    msg.set_content(msgbody if msgbody else "Script ran, but no accounts were suspended or logged.")
    
    try:
        with smtplib.SMTP(configs['SMTPServerAddress'], timeout=15) as s:
            s.send_message(msg)
        print(f"🟢 Message sent successfully.")
    except smtplib.SMTPRecipientsRefused as e:
        print(f"🔴 Error: All recipients were refused. Details: {e}")
    except smtplib.SMTPSenderRefused as e:
        print(f"🔴 Error: The sender address was refused. Details: {e}")
    except smtplib.SMTPDataError as e:
        print(f"🔴 Error: The server replied with an unexpected error code. Details: {e}")
    except socket.gaierror as e:
        print(f"🔴 Connection Error: Could not resolve the server address '{configs['SMTPServerAddress']}'. Details: {e}")
    except ConnectionRefusedError as e:
        print(f"🔴 Connection Error: The server actively refused the connection. Details: {e}")
    except smtplib.SMTPException as e:
        print(f"🔴 General SMTP Error: {e}")
    except Exception as e:
        print(f"🔴 An unexpected system error occurred: {e}")
        
    print('Done')

if __name__ == '__main__':
    main()