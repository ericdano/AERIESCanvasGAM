import pandas as pd
import os, sys, shlex, subprocess, gam, datetime, json, smtplib, logging
from pathlib import Path
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
import glob
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler


"""
Python 3.14


"""

start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
#Logging

logger = logging.getLogger('ACIS Student Parent List in Google Update Script')
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
syslog_handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
formatter = logging.Formatter('%(name)s: %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
syslog_handler.setFormatter(formatter)
logger.addHandler(syslog_handler)
logger.addHandler(console_handler)



#prep status (msg) email
msg = EmailMessage()
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
WasThereAnError = False
DontDeleteFiles = False
# Change directory to a TEMP Directory where GAM and Python can process CSV files 
os.chdir(configs['PythonTempDirectory'])
#populate a table with counselor parts
counselors = [ ('acis','feinberg')]
msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
logger.info('Connecting To AERIES to get students for ACIS Counselor')
connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)
OLDthequery = f"""
SELECT ALTSCH.ALTSC, 
    STU.LN, 
    STU.SEM, 
    STU.PEM, 
    STU.GR, 
    STU.CU, 
    TCH.EM 
    FROM STU 
    INNER JOIN TCH ON STU.SC = TCH.SC 
        AND STU.CU = TCH.TN 
    INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID
    WHERE (STU.SC = 6) 
        AND STU.DEL = 0 
        AND STU.TG = \'\' 
        AND STU.CU > 0 
        AND STU.GR <= 12 
    ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN
"""
thequery = f"""
SELECT 
    CASE STU.SC
        WHEN 1 THEN 'LLHS'
        WHEN 2 THEN 'AHS'
        WHEN 3 THEN 'MHS'
        WHEN 4 THEN 'CHS'
        WHEN 6 THEN 'ACIS'
        WHEN 7 THEN 'DVCEP'
        WHEN 30 THEN 'TRANS'
    END AS ALTSC,
    STU.LN, 
    STU.SEM, 
    STU.PEM, 
    STU.GR, 
    STU.CU, 
    TCH.EM 
    FROM STU 
    INNER JOIN TCH ON STU.SC = TCH.SC 
        AND STU.CU = TCH.TN 
    WHERE (STU.SC = 6) 
        AND STU.DEL = 0 
        AND STU.TG = ''
        AND STU.CU > 0 
        AND STU.GR <= 12 
    ORDER BY 
        CASE STU.SC
            WHEN 1 THEN 'LLHS' WHEN 2 THEN 'AHS' WHEN 3 THEN 'MHS' 
            WHEN 4 THEN 'CHS' WHEN 6 THEN 'ACIS' WHEN 7 THEN 'DVCEP' WHEN 30 THEN 'TRANS'
        END, 
        STU.CU, STU.LN
"""


with engine.begin() as connection:
    logger.info('Connecting to AERIES to get Parental emails')
    sql_query1 = pd.read_sql_query(thequery,connection)
    logger.info('Closed AERIES connection')
#sql_query1.to_csv('acisstudentparentdebug.csv')
sql_query1.drop(sql_query1.columns.difference(['SEM',
                                              'PEM']), axis=1,inplace=True)
c_name = ["email"]
listylist = pd.DataFrame(columns = c_name)
listylist["email"] = pd.concat([sql_query1['SEM'],sql_query1['PEM']],axis=0, ignore_index=True)
header = ["email"]
listylist.to_csv('acisstudentparents.csv',index = False, header = False, columns = header)
logger.info('Running GAM')
stat1 = gam.CallGAMCommand(['gam','update', 'group', 'acisgrades9to12studentsandparents', 'sync', 'members', 'file', 'acisstudentparents.csv'])
if stat1 != 0:
    WasThereAnError = True
    logger.error('GAM returned an error from last command')
if not DontDeleteFiles:
    os.remove('acisstudentparents.csv')
msgbody += f'Synced ACIS Student Parent list. Gam Status->{stat1}\n' 
msgbody+='Done!'
logger.info('Done Syncing to Google Groups')
if WasThereAnError:
    msg['Subject'] = f"🔴 ERROR! {configs['SMTPStatusMessage']} AUHSD ACIS Grades 9 to 12 Student and Parents to Google Groups {datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")}"
    logger.error( f"🔴 ERROR! {configs['SMTPStatusMessage']} AUHSD ACIS Grades 9 to 12 Student and Parents to Google Groups {datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")}")
else:
    msg['Subject'] = f"🟢 {configs['SMTPStatusMessage']} AUHSD ACIS Grades 9 to 12 Student and Parents to Google Groups {datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")}"
    logger.info(f"🟢 {configs['SMTPStatusMessage']} AUHSD ACIS Grades 9 to 12 Student and Parents to Google Groups {datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")}")
end_of_timer = timer()
msgbody += f'\n\n Elapsed Time={end_of_timer - start_of_timer}\n'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
logger.info('Sent status message')
logger.info(f'Done - Took {end_of_timer - start_of_timer}')

