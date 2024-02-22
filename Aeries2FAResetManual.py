import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from io import StringIO
from pathlib import Path
from ssl import SSLSocket
from timeit import default_timer as timer
import pandas as pd
import ldap3
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

"""
 Python 3.9+ script to RESET 2FA in AERIES
"""
'''
def authenticate():
    conn = ldap3.initialize('ldap://acalanes.k12.ca.us')
    conn.protocol_version = 3
    conn.set_option(ldap3.OPT_REFERRALS,0)
    try:
        username = ''
if __name__ == '__main__':

    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    #prep status (msg) email
    
    


'''
WasThereAnError = False
start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
    configs = json.load(f)
msg = EmailMessage()
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = "serveradmins@auhsdschools.org"
msgbody = ''
msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
os.chdir('E:\\PythonTemp')
mfa2reset = 'auhsd\edannewitz'
connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESTechDept'] + ";PWD=" + configs['AERIESTechDeptPW'] + ";"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)
result = engine.execute("""UPDATE UGN SET MFA =0 WHERE UN ='auhsd\nsingleterry'""")
if WasThereAnError:
    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AERIES 2FA Reset " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    msgbody += "Errors resetting 2FA on " + mfa2reset + "\n"
else:
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " AERIES 2FA Reset " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    msgbody += "No errors resetting 2FA on account " + mfa2reset + "\n"
end_of_timer = timer()
msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
