import pandas as pd
import os, sys, shlex, subprocess, json, logging, smtplib, datetime
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from timeit import default_timer as timer
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

WasThereAnErr = False
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

CounselorCSV = Path.home() / ".Acalanes" / "CanvasCounselingGroups.csv"
thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Loaded config file and logfile started for AUHSD Counseling Canvas')
thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Loading Counseling CSV file')
#prep status (msg) email
msg = EmailMessage()
MessageSub1 = str(configs['SMTPStatusMessage'] + " AUHSD Counseling To Canvas " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
# The counseling CSV has counselors email address, there sis_id, canvas group and grade
# Grade can have a field All in it that it will then place into a All students
# at site group for the counselor
CounselorCanvasSection = pd.read_csv(CounselorCSV)
msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'

connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)
#-----Canvas Info
Canvas_API_URL = configs['CanvasBETAAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Connecting to Canvas')
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
# Go through the counseling list, then add or remove students from groups
msgbody += 'Starting Canvas Counselor Groups for AUHSD Script\n'
for i in CounselorCanvasSection.index:
  CounselorEmail = CounselorCanvasSection['email'][i]
  GradeToGet = CounselorCanvasSection['Grade'][i]
  print('Processing info for ' + str(CounselorEmail) + ' Grade->' + str(GradeToGet))
  CanvasSectionID = CounselorCanvasSection['CanvasSectionID'][i]
  msgbody += 'Matching for ' + CounselorEmail + ' - Counselor->' + str(CounselorEmail) + ' - Grade->' + str(GradeToGet) + ' - Canvas Group ID->' + str(CanvasSectionID) + '\n'
  aeriesSQLData = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.ID, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 AND EM = \'' + CounselorEmail + '\' AND GR = \'' + str(GradeToGet) + '\'',engine)
  thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Making SET of Aeries IDs')
  # Now go get the group off Canvas
  msgbody += 'Getting exisiting users from group id->' + str(CanvasSectionID) + '\n'
  #
  section = canvas.get_section(CounselorCanvasSection['CanvasSectionID'][i],include=["students"])
  # make a dataframe that has Student SIS IDs in it
  canvasdf = pd.DataFrame(columns=['ID'])
  for s in section.students:
    tempDF = pd.DataFrame([{'ID': s['sis_user_id']}])
    canvasdf = pd.concat([canvasdf,tempDF], axis=0, ignore_index=True)


  studentsinaeriesnotincanvas = aeriesSQLData['ID'][~aeriesSQLData['ID'].isin(canvasdf['ID'])].unique()
  studentsincanvasnotinaeries = canvasdf['ID'][~canvasdf['ID'].isin(aeriesSQLData['ID'])].unique()
  print('Students in Aeries not in Canvas')
  print(studentsinaeriesnotincanvas)
  print('Students in Canvas not in AERIES')
  print(studentsincanvasnotinaeries)
  exit(1)
  for student in studentstoremove:
    thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Looking up student->'+str(student)+' in Canvas')
    msgbody += 'Looking up student->'+str(student)+' in Canvas' + '\n'
    print('Looking up student->'+str(student)+' in Canvas')
    try:
      user = canvas.get_user(str(student),'sis_user_id')
    except CanvasException as g:
      if str(g) == "Not Found":
        print('Cannot find user sis_id->'+str(student))
        msgbody+='<b>Canvas cannot find user sis_id->'+str(student) + ', might be a new student who is not in Canvas yet</b>\n'
        WasThereAnErr = True
        thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Cannot find user sis_id->'+str(student))
    else:
      try:
        n = group.remove_user(user.id)
      except CanvasException as e:
        if str(e) == "Not Found":
            print('User not in group CanvasID->' + str(user.id) + ' sis_id->'+ str(student))
            msgbody += 'User not in group CanvasID->' + str(user.id) + ' sis_id->'+ str(student) + '\n'
            thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Some sort of exception happened when removing student->'+str(student)+' from Group')
      print('Removed Student->'+str(student)+' from Canvas group')
      msgbody += 'Removed Student->'+str(student)+' from Canvas group' + '\n'
      thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Removed Student->'+str(student)+' from Canvas group')
  # Now add students to group
  for student in studentstoadd:
    msgbody += 'going to try to add '+ str(student) + ' to group ' + str(CanvasGroupID) + '\n'
    try:
      user = canvas.get_user(str(student),'sis_user_id')
    except CanvasException as f:
      if str(f) == "Not Found":
        print('Cannot find user id->'+str(student))
        msgbody += '<b>Cannot find user id->'+str(student) + ' might be a new student who is not in Canvas yet</b>\n'
        WasThereAnErr = True
        thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Cannot find user id!')
    else:    
      try:
        n = group.create_membership(user.id)
      except CanvasException as e:
        if str(e) == "Not Found":
          print('User not in group')
          msgbody += 'User not in group ' + str(user.id) + '\n'
          WasThereAnErr = True
      print('Added Student id->'+str(student)+' to Canvas group->' + str(CanvasGroupID))
      msgbody += 'Added Student id->'+str(student)+' to Canvas group->' + str(CanvasGroupID) + '\n'
      thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Added Student id->'+str(student)+' to Canvas group->' + str(CanvasGroupID))
thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Closed AERIES connection')
msgbody+='Done!'
end_of_timer = timer()
if WasThereAnErr:
  msg['Subject'] = "Error! - " + MessageSub1
else:
  msg['Subject'] = MessageSub1
msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Sent Status Message')
thelogger.info('CanvasGroups_CounselorsToCanvasGroup->Done!' + str(end_of_timer - start_of_timer))
print('Done!!!')
