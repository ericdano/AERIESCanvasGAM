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
output_dir = "E:\\PythonTemp"
msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
Sites = {'Site':['AHS','CHS','LLHS','MHS','ACIS'],
         'SiteNum':[1,2,3,4,6]}
sitesdf = pd.DataFrame(Sites)
QueryStr = f"SELECT STU.SEM, STU.GR, STU.SC FROM STU ORDER BY STU.SC, STU.GR"
thelogger.info(f"Student Google Group Updater Gathering all students")
connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)
with engine.begin() as connection:
    #thelogger.info('UpdateACISStuParentListsInGoogle->Connecting to AERIES to get Parental emails')
    df= pd.read_sql_query(QueryStr,connection)
    #thelogger.info('UpdateACISStuParentListsInGoogle->Closed AERIES connection')
#for index,row in df.iterrows():
#    for i in range(9,13):
# We just care about STU.SEM and STU.GR and STU.SC
print(sql_query1)
sc_mapping = {
    1: 'AHS',
    2: 'LLHS',
    3: 'CHS',
    4: 'MHS',
    5: 'E',
    6: 'ACIS'
}
df['SC'] = df['SC'].replace(sc_mapping)
print("Updated DataFrame with 'SC' values replaced:")
print(df.head())
df['GR'] = df['GR'].apply(lambda x: f"GR {x}")
print("\nUpdated DataFrame with 'GR' values modified:")
print(df.head())
Grouped = df.groupby(['SC','GR'])
print(Grouped)
print("Iterating through groups and creating CVS")
for name, group_df in Grouped:
    file_name = f"{'_'.join(name).replace(' ', '_')}.csv"
    output_path = os.path.join(output_dir, file_name)
    group_df[['SEM']].to_csv(output_path, index=False)
    print(f"Saved {name}")
print("\nProcess complete.")
#c_name = ["email"]
#listylist = pd.DataFrame(columns = c_name)
#listylist["email"] = pd.concat([sql_query1['SEM'],sql_query1['PEM']],axis=0, ignore_index=True)
#header = ["email"]
#listylist.to_csv('acisstudentparents.csv',index = False, header = False, columns = header)
#thelogger.info('UpdateACISStuParentListsInGoogle->Running GAM')
#stat1 = gam.CallGAMCommand(['gam','update', 'group', 'acisgrades9to12studentsandparents', 'sync', 'members', 'file', 'acisstudentparents.csv'])
#if stat1 != 0:
#    WasThereAnError = True
#    thelogger.info('UpdateACISStuParentListsInGoogle->GAM returned an error from last command')
#if not DontDeleteFiles:
#    os.remove('acisstudentparents.csv')
#msgbody += 'Synced ACIS Student Parent list. Gam Status->' + str(stat1) + '\n' 
#msgbody+='Done!'
#thelogger.info('UpdateACISStuParentListsInGoogle->Done Syncing to Google Groups')
#if WasThereAnError:
#    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AUHSD ACIS Grades 9 to 12 Student and Parents to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
#else:
#    msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD ACIS Grades 9 to 12 Student and Parents to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
#end_of_timer = timer()
#msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
#msg.set_content(msgbody)
#s = smtplib.SMTP(configs['SMTPServerAddress'])
#s.send_message(msg)
#thelogger.info('UpdateACISStuParentListsInGoogle->Sent status message')
#thelogger.info('UpdateACISStuParentListsInGoogle->Done - Took ' + str(end_of_timer - start_of_timer))

