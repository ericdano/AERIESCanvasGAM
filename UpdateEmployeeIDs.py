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
 Python 3.9+
"""

if __name__ == '__main__':
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    #prep status (msg) email
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = 'edannewitz@auhsdschools.org'
    msgbody = ''
    WasThereAnError = False
    GC_SERVER = 'ldap://acalanes.k12.ca.us:3268' 
    SEARCH_BASE = 'DC=acalanes,DC=k12,DC=ca,DC=us'
    BIND_USER = 'tech@acalanes.k12.ca.us'
    BIND_PASSWORD = configs['ADPassword']
    # Define your specific target OUs across the two domains
    TARGET_OUS = [
        'OU=AUHSD Staff,DC=acalanes,DC=k12,DC=ca,DC=us',
        'OU=Acad Staff,DC=staff,DC=acalanes,DC=k12,DC=ca,DC=us'
    ]
    dest_filename = "asbworks_acalanes.csv"
    thelogger.info('Update ASB Works->Starting ASB Works Script')
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'

    # Get AERIES Data
    os.chdir('E:\\PythonTemp')
    thelogger.info('Update ASB Works->Connecting To AERIES to get ALL students Data')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    AllEmployeeIDs = f"""
    SELECT em, LN, HRID FROM STF
    """
    sql_query = pd.read_sql_query(AllEmployeeIDs, engine)
    print(sql_query)
    # Find AD entries with no employeeID
    # The filter you requested: Missing ID AND Not Disabled
    SEARCH_FILTER = '(&(objectCategory=person)(objectClass=user)(!(employeeID=*))(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'

    server = Server(GC_SERVER, get_info=ALL)

    with Connection(server, user=BIND_USER, password=BIND_PASSWORD, auto_bind=True) as conn:
        print(f"Starting targeted search for active users missing employeeIDs...\n")
        
        all_found_users = []

        for ou_path in TARGET_OUS:
            print(f"Checking OU: {ou_path}...")
            
            conn.search(
                search_base=ou_path,
                search_filter=SEARCH_FILTER,
                attributes=['cn', 'sAMAccountName', 'distinguishedName'],
                search_scope='SUBTREE' # This looks inside the OU and any sub-OUs
            )
            
            all_found_users.extend(conn.entries)

        # 2. Output Results
        print(f"\nSearch Complete. Found {len(all_found_users)} users.")
        print("-" * 60)
        print(f"{'Username':<20} | {'Common Name':<30}")
        print("-" * 60)

        for entry in all_found_users:
            print(f"{entry.sAMAccountName.value:<20} | {entry.cn.value:<30}")
    exit(1)
    #sql_query.to_csv(dest_filename, index = False)
    thelogger.info('Update ASB Works->Wrote temp CSV to disk')
    msgbody += "Got AERIES data, connecting to FTPS\n"
    thelogger.info('Update ASB Works->Connecting to ASB Works via FTPS')
    #exit(1)

    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " ASB Works Upload " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " ASB Works Upload " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
