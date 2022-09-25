import pandas as pd
import os, sys, shlex, subprocess, json, logging, smtplib, datetime
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from timeit import default_timer as timer
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging
if configs['logserveraddress'] is None:
    logfilename = Path.home() / ".Acalanes" / configs['logfilename']
    thelogger = logging.getLogger('MyLogger')
    thelogger.basicConfig(filename=str(logfilename), level=thelogger.info)
else:
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)

thelogger.info('CanvasGroups_ACISCounselingToCanvas->Loaded config file and logfile started for ACIS Counseling Canvas')
#prep status (msg) email
msg = EmailMessage()
msg['Subject'] = str(configs['SMTPStatusMessage'] + " ACIS Counseling To Canvas " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
#-----Canvas Info
Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
thelogger.info('CanvasGroups_ACISCounselingToCanvas->Connecting to Canvas')
account = canvas.get_account(1)
#Set up Counselors to pull from Aeries along with the Canvas groups they are part of
# School, Counselor lastname, the Canvas Group ID, counselors ID in Aeries/Canvas
counselors = [ ('acis','feinberg',10831,103276)]
msgbody += 'Starting Canvas Counseler Groups for ACIS Script\n'
connection_string = "DRIVER={SQL Server};SERVER=SATURN;DATABASE=DST22000AUHSD;Trusted_Connection=yes"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)
thelogger.info('CanvasGroups_ACISCounselingToCanvas->Getting data from AERIES')
dataframe1 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.ID, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',engine)
pd.set_option('display.max_rows',dataframe1.shape[0]+1)
#Now make a set of JUST the SIS_USER_IDs from Aeries
thelogger.info('CanvasGroups_ACISCounselingToCanvas->Making SET of Aeries IDs')
aerieslist = set(dataframe1.ID)
print('Making Sets for comparison')
#Get Exisiting users SIS_USER_ID from Counseling Group
thelogger.info('CanvasGroups_ACISCounselingToCanvas->Getting users in ACIS Canvas group')
group = canvas.get_group(10831,include=['users'])
dataframe2 = pd.DataFrame(group.users,columns=['sis_user_id'])
#pd.set_option('display.max_rows',dataframe2.shape[0]+1)
#print(dataframe2)

#Make a set of JUST SIS_USER_IDs that are currently in the Canvas Group
canvaslist = set(pd.to_numeric(dataframe2.sis_user_id))
#Subtract items from the Aeries set that are in the Canvas set
#The resulting set is the SIS_IDs we need to ADD to the Group
studentstoadd = aerieslist - canvaslist
#Subtract items from Canvaslist set that are in Aeries set. 
#These are students that need to be removed from the group
studentstoremove = canvaslist - aerieslist
#Keep the teacher in the group though, so take them OUT of the set
studentstoremove.remove(counselors[0][3]) # Keep teacher in canvas group
print('Processing ACIS Students')
msgbody += 'Looking for Students to remove from groups\n'
for student in studentstoremove:
  thelogger.info('CanvasGroups_ACISCounselingToCanvas->Looking up student->'+str(student)+' in Canvas')
  try:
    user = canvas.get_user(str(student),'sis_user_id')
  except CanvasException as g:
    if str(g) == "Not Found":
      print('Cannot find user sis_id->'+str(student))
      msgbody += '<b>Cannot find user sis_id->'+str(student) + ', might be a new student not in Canvas yet</b>\n'
      thelogger.critical('CanvasGroups_ACISCounselingToCanvas->Cannot find user sis_id->'+str(student))
  else:
    try:
      n = group.remove_user(user.id)
    except CanvasException as e:
      if str(e) == "Not Found":
          print('User not in group')
          thelogger.critical('CanvasGroups_ACISCounselingToCanvas->Some sort of exception happened when removing student->'+str(student)+' from Group')
    print('Removed Student->'+str(student)+' from Canvas group')
    msgbody +='Removed Student->'+str(student)+' from Canvas group \n'
    thelogger.info('CanvasGroups_ACISCounselingToCanvas->Removed Student->'+str(student)+' from Canvas group')
# Now add students to group
msgbody += 'Looking for students to add to group\n'
for student in studentstoadd:
  print('going to try to add'+str(student))
  try:
    user = canvas.get_user(str(student),'sis_user_id')
  except CanvasException as f:
    if str(f) == "Not Found":
      print('Cannot find user id->'+str(student))
      thelogger.critical('CanvasGroups_ACISCounselingToCanvas->Cannot find user id->'+str(student)+'to add to group')
  else:
    try:
      n = group.create_membership(user.id)
    except CanvasException as e:
      if str(e) == "Not Found":
        print('User not in group')
        thelogger.critical('CanvasGroups_ACISCounselingToCanvas->Student id->'+str(student)+' not found in Canvas')
    print('Added Student id->'+str(student)+' to Canvas group')
    msgbody += 'Added Student id->'+str(student)+' to Canvas group \n'
    thelogger.info('CanvasGroups_ACISCounselingToCanvas->Added Student id->'+str(student)+' to Canvas group')
msgbody+='Done!'
end_of_timer = timer()
msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
thelogger.info('CanvasGroups_ACISCounselingToCanvas->Sent Status Message')
thelogger.info('CanvasGroups_ACISCounselingToCanvas->Done! - Took ' + str(end_of_timer - start_of_timer))
print('Done!!!')