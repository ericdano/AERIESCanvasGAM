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

start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
#Logging
thelogger = logging.getLogger('MyLogger')
thelogger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
thelogger.addHandler(handler)
#prep status (msg) email
msg = EmailMessage()
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
WasThereAnError = False
DontDeleteFiles = False
# Change directory to a TEMP Directory where GAM and Python can process CSV files 
os.chdir('E:\\PythonTemp')
#populate a table with counselor parts
counselors = [ ('acis','feinberg')]
msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
thelogger.info('All Campus Student Canvas Groups->Connecting To AERIES to get ALL students for Campus')
connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)
with engine.begin() as connection:
    thelogger.info('UpdateACISStuParentListsInGoogle->Connecting to AERIES to get Parental emails')
    sql_query1 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.PEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 AND STU.GR <= 12 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',connection)
    thelogger.info('UpdateACISStuParentListsInGoogle->Closed AERIES connection')
#sql_query1.to_csv('acisstudentparentdebug.csv')
sql_query1.drop(sql_query1.columns.difference(['SEM',
                                              'PEM']), axis=1,inplace=True)
c_name = ["email"]
listylist = pd.DataFrame(columns = c_name)
listylist["email"] = pd.concat([sql_query1['SEM'],sql_query1['PEM']],axis=0, ignore_index=True)
header = ["email"]
listylist.to_csv('acisstudentparents.csv',index = False, header = False, columns = header)
thelogger.info('UpdateACISStuParentListsInGoogle->Running GAM')
stat1 = gam.CallGAMCommand(['gam','update', 'group', 'acisgrades9to12studentsandparents', 'sync', 'members', 'file', 'acisstudentparents.csv'])
if stat1 != 0:
    WasThereAnError = True
    thelogger.info('UpdateACISStuParentListsInGoogle->GAM returned an error from last command')
if not DontDeleteFiles:
    os.remove('acisstudentparents.csv')
msgbody += 'Synced ACIS Student Parent list. Gam Status->' + str(stat1) + '\n' 
msgbody+='Done!'
thelogger.info('UpdateACISStuParentListsInGoogle->Done Syncing to Google Groups')
if WasThereAnError:
    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AUHSD ACIS Grades 9 to 12 Student and Parents to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
else:
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD ACIS Grades 9 to 12 Student and Parents to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
end_of_timer = timer()
msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
thelogger.info('UpdateACISStuParentListsInGoogle->Sent status message')
thelogger.info('UpdateACISStuParentListsInGoogle->Done - Took ' + str(end_of_timer - start_of_timer))
print('Done!!!')
