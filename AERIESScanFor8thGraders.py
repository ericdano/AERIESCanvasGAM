import io, ftplib, ssl, sys, os, datetime, json, gam, smtplib, logging
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
 Python 3.11+
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
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    msg = MIMEMultipart()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = 'edannewitz@auhsdschools.org'
    DontDeleteFiles = False
    WasThereAnError = False
    filenamestring = 'csvtosheet.csv'
    thelogger.info('AERIES Scan for New Students->Connecting To AERIESa')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    eighthgraders = f"""
    select * from stu where gr = 8 and sem = '' and sc < 8
    """
    sql_query = pd.read_sql_query(eighthgraders, engine)
    print(sql_query)
    os.chdir('E:\\PythonTemp')
    sql_query.to_csv(filenamestring,index=False)
    sheetid = "1LS6y12eGNHJ9uG2i6Sswjr7Bata0ZmwZXPWyGZ-xYJ4"
    gam.initializeLogging()
    stat1 = gam.CallGAMCommand(['gam','csv', 'csvtosheet.csv', 'gam', 'user', 'edannewitz@auhsdschools.org', 'add', 'sheet', '1LS6y12eGNHJ9uG2i6Sswjr7Bata0ZmwZXPWyGZ-xYJ4','csvdata','*'])
    if stat1 != 0:
        WasThereAnError = True
        thelogger.critical('UpdateStudentListsInGoogle->GAM returned an error for the last command')
    if not DontDeleteFiles:
        try:
            os.remove(filenamestring)
        except:
            print('Error')
    print('Done')
    """
            msgbody += f"Error removing {campus[0]} ALL grades list.\n" 
            thelogger.critical(f"UpdateStudentListsInGoogle->Error trying to remove file {counselor[1]} ALL Grades list csv")
    msgbody += f"Synced Students-> All list. Gam Status->{stat1}\n" 


    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AERIES New Student Scan " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " AERIES New Student Scan " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    msg.attach(MIMEText(html_body,'html'))
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    """
