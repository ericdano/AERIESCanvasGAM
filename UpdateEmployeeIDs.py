import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE
from io import StringIO
from pathlib import Path
from timeit import default_timer as timer
import pandas as pd
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler


"""
2026 - Script to update Active Directory EmployeeID attributes from Aeries data if the EmployeeID is missing in AD but present in Aeries.

Python 3.9+

"""


def send_success_report(df_final, configs):
    total_matches = len(df_final)
    summary_table = df_final[['Name', 'Email', 'ID']].to_html(index=False, justify='left', classes='red-table')
    
    html_body = f"""
    <html>
        <head>
        <style>
            table {{ 
                border-collapse: collapse; 
                width: 100%; 
                font-family: sans-serif; 
                margin-bottom: 20px;
            }}
            th {{ 
                background-color: #f2f2f2; 
                font-weight: bold; 
                padding: 8px; 
                border: 1px solid #ddd; 
                color: black;
            }}
            td {{ 
                padding: 8px; 
                border: 1px solid #ddd; 
            }}
            
            /* Target only the table with the 'red-table' class */
            .red-table td {{ 
                color: #FF0000; 
            }}
            
            /* Target only the table with the 'black-table' class */
            .black-table td {{ 
                color: #000000; 
            }}
        </style>
        </head>
        <body>
            <p>The Active Directory EmployeeID update process has completed successfully.</p>
            <p>Total Records Updated: {total_matches}</p>
            <p>Summary of Matched Records:</p>
            <p>------------------------------------------------------------</p>
            {summary_table}
            <p><p>
            <p>------------------------------------------------------------</p>
            <p>This report was generated automatically via Python.</p>
        </body>
    </html>
    """
    msg = MIMEMultipart()
    timestamp = datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")
    msg['Subject'] = f"AD EmployeeID Update: Success Report {timestamp}"
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = 'edannewitz@auhsdschools.org'
    msg.attach(MIMEText(html_body, 'html'))

    try:
        # Using 'with' automatically handles s.quit() even if an error occurs
        with smtplib.SMTP(configs['SMTPServerAddress'], timeout=10) as s:
            # Uncomment if your server requires authentication:
            # s.starttls()
            # s.login(configs['user'], configs['pass'])
                
            s.send_message(msg)
            print(f"Email sent successfully")
            return True

    except smtplib.SMTPConnectError:
        print("Error: Could not connect to the SMTP server. Check the address/port.")
    except smtplib.SMTPAuthenticationError:
        print("Error: SMTP Authentication failed. Check your credentials.")
    except Exception as e:
        print(f"An unexpected error occurred while sending email: {e}")
        
    return False

def update_ad_employee_ids(dataframe, bind_user, bind_password):
    updated_count = 0
    error_count = 0

    # Grouping by server ensures we only connect once per domain
    for server_url in dataframe['Server'].unique():
        server_df = dataframe[dataframe['Server'] == server_url]
        
        print(f"\nConnecting to {server_url} to perform updates...")
        server = Server(server_url, get_info=ALL)
        
        with Connection(server, user=bind_user, password=bind_password, auto_bind=True) as conn:
            for index, row in server_df.iterrows():
                target_dn = row['DN']
                new_id = str(row['ID']).strip() # Ensure it's a string for AD
                
                # Perform the modification
                success = conn.modify(
                    target_dn, 
                    {'employeeID': [(MODIFY_REPLACE, [new_id])]}
                )
                
                if success:
                    print(f" [SUCCESS] Updated {row['Username']} to ID {new_id}")
                    updated_count += 1
                else:
                    print(f" [FAILED]  Could not update {row['Username']}. Error: {conn.result['description']}")
                    error_count += 1

    print(f"\n--- Update Summary ---")
    print(f"Total Successful: {updated_count}")
    print(f"Total Failed:     {error_count}")

# Execute the update
# CAUTION: This will write changes to your Active Directory.
def GetAERIESData(configs):
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    AllEmployeeIDs = f"""
    SELECT em, LN, ID FROM STF
    """
    AeriesEmployees = pd.read_sql_query(AllEmployeeIDs, engine)
    print(AeriesEmployees)
    return AeriesEmployees

def GetADUsersMissingEmployeeID(configs,BIND_USER,BIND_PASSWORD):
    # Find AD entries with no employeeID
    # The filter you requested: Missing ID AND Not Disabled
    # Configuration - Explicitly using Port 389 for full attribute access
    GC_SERVER = 'ldap://acalanes.k12.ca.us:3268' 
    SEARCH_BASE = 'DC=acalanes,DC=k12,DC=ca,DC=us'

    # Define your specific target OUs across the two domains
    TARGET_OUS = [
        'OU=AUHSD Staff,DC=acalanes,DC=k12,DC=ca,DC=us',
        'OU=Acad Staff,DC=staff,DC=acalanes,DC=k12,DC=ca,DC=us'
    ]
    # Active Directory Configuration
    DOMAINS = [
        {'server': 'ldap://acalanes.k12.ca.us:389', 'base': 'OU=AUHSD Staff,DC=acalanes,DC=k12,DC=ca,DC=us'},
        {'server': 'ldap://staff.acalanes.k12.ca.us:389', 'base': 'OU=Acad Staff,DC=staff,DC=acalanes,DC=k12,DC=ca,DC=us'}
    ]
    BIND_USER = 'tech@acalanes.k12.ca.us'
    BIND_PASSWORD = configs['ADPassword']
    SEARCH_FILTER = '(&(objectCategory=person)(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'
    # --- STEP 1: Extract AD Users Missing employeeID ---
    user_data = []
    for domain in DOMAINS:
        server = Server(domain['server'], get_info=ALL)
        with Connection(server, user=BIND_USER, password=BIND_PASSWORD, auto_bind=True) as conn:
            conn.search(domain['base'], SEARCH_FILTER, attributes=['cn', 'sAMAccountName', 'employeeID', 'mail', 'distinguishedName'])
            for entry in conn.entries:
                # Check for missing/blank ID
                eid = str(entry.employeeID.value).strip() if 'employeeID' in entry and entry.employeeID.value else ""
                email = str(entry.mail.value).strip() if 'mail' in entry and entry.mail.value else None
                
                user_data.append({
                    'Name': entry.cn.value, 
                    'Username': entry.sAMAccountName.value, 
                    'Email': email, 
                    'EmployeeID_AD': eid, 
                    'DN': entry.distinguishedName.value,
                    'Server': domain['server'] # Track which server to write back to
                })

    df_ad = pd.DataFrame(user_data)
    df_missing_id = df_ad[(df_ad['EmployeeID_AD'] == "") & (df_ad['Email'].notna())].copy()

    # --- STEP 2: Match with Aeries using 'ID' ---
    # Normalize columns for a robust match
    df_missing_id['Email_Match'] = df_missing_id['Email'].str.lower().str.strip()
    return df_missing_id

if __name__ == '__main__':
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    thelogger.info('Update Employee ID->Starting AERIES cript')
    WasThereAnError = False
    BIND_USER = 'tech@acalanes.k12.ca.us'
    BIND_PASSWORD = configs['ADPassword']
    # Get AERIES Data
    thelogger.info('Update Employee ID->Connecting To AERIES to get ALL students Data')
    AeriesEmployees = GetAERIESData(configs)
    thelogger.info('Update Employee ID->Successfully got AERIES Data')
    AeriesEmployees['EM_Match'] = AeriesEmployees['em'].astype(str).str.lower().str.strip()
    # Get AD Users Missing EmployeeID
    thelogger.info('Update Employee ID->Connecting To AD to get users missing Employee IDs')    
    df_missing_id = GetADUsersMissingEmployeeID(configs,BIND_USER,BIND_PASSWORD)
    # Merge: Keeping only matches and carrying over the 'ID' column
    df_final_matches = pd.merge(
        df_missing_id, 
        AeriesEmployees[['EM_Match', 'ID']], 
        left_on='Email_Match', 
        right_on='EM_Match', 
        how='inner'
    )

    # Clean up temporary merge columns
    df_final_matches = df_final_matches.drop(columns=['Email_Match', 'EM_Match'])
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    # --- STEP 3: Output Results ---
    if not df_final_matches.empty:
        print(f"Success! Found {len(df_final_matches)} users to update.")
        print(df_final_matches[['Name', 'Email', 'ID']])
    else:
        print("No matches found. Check that Aeries emails match AD exactly.")
    update_ad_employee_ids(df_final_matches, BIND_USER, BIND_PASSWORD)
    send_success_report(df_final_matches,configs)
