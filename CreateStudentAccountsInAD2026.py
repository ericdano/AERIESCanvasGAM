import csv
import subprocess
import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from ldap3 import Server, Connection, ALL
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
This script is a hybrid of Python and Powershell
Acalanes Union High School District uses AERIES, but we aren't strictly bound to Google
nor are we really Active Directory. We are somewhere inbetween.

One of the issues is creating students. We formerly used a solution developed by
Tools4Ever that was some sort of scripting thing that trolled through the AERIES 
Database and moved or created students accounts.

However, it was slow. Real slow. And would more often than not mess up students 
either deactivating them incorrectly, and other issues. PLUS it was EOL and Tools4Ever
wanted a lot of money to redo this script/automation.

Not for production. Still under development 3-12-2026

"""
# --- Configuration Variables ---
OU = "OU=Freshman,OU=MHS,OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us"
CSV_PATH = Path(r"H:\MHS_FRESHMAN_2025.csv")
GROUP_1 = "MHS Grade 9 Students"
GROUP_2 = "KIX_MHSACAD"
AD_DESCRIPTION = "MHS Grade 9 Student"
SERVER = "socrates"

def scan_aeries_for_new_students(configs):
    WasThereAnError = False
    thelogger.info('AERIES Scan for New Students->Connecting To AERIESa')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    NewStudents = f"""
    select * from stu where tg='' and del = 0 and sem = '' and sc < 8
    """
    sql_query = pd.read_sql_query(NewStudents, engine)
    print(sql_query)
    html_table_NewStudents = sql_query.to_html(index=False, justify='left', classes='red-table')
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
            <p>New Students in AERIES without Emails:</p>
            <p><i>Ran this SQL query:</i> {NewStudents}</p>
            {html_table_NewStudents}
            <p></p>
        """
    if sql_query.empty:
        html_body += f"""<p>There seem to be no new students without emails.</p>
        <p><p>"""
    html_body += f"""
            <p>Elapsed Time: {timer() - start_of_timer} seconds</p>
        </body>
        </html>"""

    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AERIES New Student Scan " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " AERIES New Student Scan " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))


def run_powershell(script: str) -> None:
    """Executes a PowerShell script block and prints any errors."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Error executing AD command: {result.stderr.strip()}")

def main():
    if not CSV_PATH.exists():
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    # Open and read the CSV file
    # Using 'utf-8-sig' to handle potential Byte Order Marks (BOM) from Excel
    with open(CSV_PATH, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            # Extract fields from the CSV
            # (Ensure these keys match your CSV header columns exactly)
            stuid = row.get('STUID', '')
            first_name = row.get('FN', '')
            last_name = row.get('LN', '')
            email = row.get('EMAIL', '')
            password = row.get('Password', '')
            h_drive_path = row.get('HDrive', '')
            display_name_csv = row.get('DISPLAYNAME', '')

            sam_account_name = stuid
            display_name = f"{last_name}, {first_name}"
            
            # Note: Changed this to use the email to fix the bug in the PS script. 
            # If you specifically need the UPN to be the Student ID, change `email` to `stuid`.
            user_principal_name = email 

            print(f"Processing user: {sam_account_name} ({display_name})...")

            # 1. Create the AD User via PowerShell wrapper
            ps_create_user = f"""
            Import-Module ActiveDirectory
            $SecurePass = ConvertTo-SecureString '{password}' -AsPlainText -Force
            New-ADUser -Server '{SERVER}' `
                       -Name '{display_name_csv}' `
                       -GivenName '{first_name}' `
                       -Surname '{last_name}' `
                       -SamAccountName '{sam_account_name}' `
                       -DisplayName '{display_name}' `
                       -UserPrincipalName '{user_principal_name}' `
                       -Path '{OU}' `
                       -AccountPassword $SecurePass `
                       -Enabled $true `
                       -EmailAddress '{email}' `
                       -ChangePasswordAtLogon $false `
                       -PasswordNeverExpires $true `
                       -CannotChangePassword $true `
                       -HomeDrive 'H:' `
                       -HomeDirectory '{h_drive_path}' `
                       -Description '{AD_DESCRIPTION}'
            """
            run_powershell(ps_create_user)

            # 2. Add User to AD Groups
            ps_add_groups = f"""
            Import-Module ActiveDirectory
            Add-ADGroupMember -Server '{SERVER}' -Identity '{GROUP_1}' -Members '{sam_account_name}'
            Add-ADGroupMember -Server '{SERVER}' -Identity '{GROUP_2}' -Members '{sam_account_name}'
            """
            run_powershell(ps_add_groups)
            
            print(f"User {sam_account_name} {display_name} created in Active Directory.")

            # 3. Create Home Directory and Set Permissions
            if h_drive_path:
                home_dir = Path(h_drive_path)
                if not home_dir.exists():
                    home_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Use standard Windows icacls to set directory permissions
                    # (OI)(CI) = Object & Container Inherit, (F) = Full Control
                    # /inheritance:r removes inherited permissions from the parent directory
                    icacls_cmd = f'icacls "{home_dir}" /grant "{sam_account_name}:(OI)(CI)(F)" /inheritance:r'
                    
                    subprocess.run(icacls_cmd, shell=True, capture_output=True)
                    print(f"Home directory {home_dir} created and permissions set.")

if __name__ == "__main__":
    main()