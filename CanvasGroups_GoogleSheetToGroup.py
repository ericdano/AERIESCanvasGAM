import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json, logging, smtplib, datetime, gam
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging
#SheetsToGroupsCSV = Path.home() / ".Acalanes" / "SheetsToCanvasGroups.csv"
logfilename = Path.home() / ".Acalanes" / configs['logfilename']
logging.basicConfig(filename=str(logfilename), level=logging.INFO)
logging.info('Loaded config file and logfile started for AUHSD Google Sheets to Canvas')
logging.info('Loading CSV file')
#prep status (msg) email
msg = EmailMessage()
msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD Groups from Sheets To Canvas " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
# The Groups CSV has to have the teacher/staff email address, there login_id, canvas group and grade
# Grade can have a field All in it that it will then place into a All students
# at site group for the counselor
# format of the CSV is 
# StaffEmail, SheetFileID, CanvasGroupID
# Pull Master List down from Google
MasterListID = '1CDj-hq5MkKStZObMi9XKGDrSSvDA_SvJbXUhJkn7_ts'
SheetsToGroupsCSV = 'e:\PythonTemp\MasterListSheetsToGroups.csv'
rc2 = gam.CallGAMCommand(['gam','user', 'edannewitz@auhsdschools.org','get','drivefile','id',MasterListID,'format','csv','targetfolder','e:\PythonTemp','targetname','MasterListSheetsToGroups.csv','overwrite','true'])
SheetsToGroups = pd.read_csv(SheetsToGroupsCSV)
logging.info('Success loding CSV file')
print('CSV File loaded ok!')
#-----Canvas Info
Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
logging.info('Connecting to Canvas')
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
# Go through the counseling list, then add or remove students from groups
msgbody += 'Starting Canvas Misc Groups for AUHSD Script\n'
for i in SheetsToGroups.index:
  StaffEmail = SheetsToGroups['StaffEmail'][i]
  SheetFileID = SheetsToGroups['SheetFileID'][i]
  CanvasGroupID =int(SheetsToGroups['CanvasGroupID'][i])
  # Grab the Google Sheet and save it to CSV
  rc2 = gam.CallGAMCommand(['gam','user', 'edannewitz@auhsdschools.org','get','drivefile','id',SheetFileID,'format','csv','targetfolder','e:\PythonTemp','targetname','SheetforCanvasGroup' + str(CanvasGroupID) +'.csv','overwrite','true'])
  dataframe1 = pd.read_csv('e:\PythonTemp\SheetforCanvasGroup' + str(CanvasGroupID) + '.csv')
  os.remove('e:\PythonTemp\SheetforCanvasGroup' + str(CanvasGroupID) + '.csv')
  print('Processing info for ' + str(StaffEmail) + ' Group->' + str(CanvasGroupID))
  msgbody += 'Matching for ' + StaffEmail + ' - Canvas Group ID->' + str(CanvasGroupID) + '\n'
  logging.info('Making SET of Email Addresses')
  print('Making SET of Email Addresses')
  SheetList = set(dataframe1.email)
  #print(SheetList)
  # Now go get the group off Canvas
  msgbody += 'Getting exisiting users from group id->' + str(CanvasGroupID) + '\n'
  #print(CanvasGroupID)
  group = canvas.get_group(CanvasGroupID,include=['users'])
  #print(group)
  dataframe2 = pd.DataFrame(group.users,columns=['login_id'])
  #print(dataframe2)
  canvaslist = set(dataframe2.login_id)
  #print('Canvas')
  #print(canvaslist)

  #Subtract items from the GoogleSheet set that are in the Canvas set
  #The resulting set are the emails we need to ADD to the Group
  studentstoadd = SheetList - canvaslist

  #Subtract items from Canvaslist set that are in Aeries set. 
   #These are students that need to be removed from the group
  studentstoremove = canvaslist - SheetList
  #Keep the teacher in the group though, so take them OUT of the set
  studentstoremove.remove(StaffEmail) # Keep teacher in canvas group
#  print('Students to add')
#  print(studentstoadd)
#  print('Students to remove')
#  print(studentstoremove)
  for student in studentstoremove:
    logging.info('Looking up student->'+student+' in Canvas')
    msgbody += 'Looking up student->'+student+' in Canvas' + '\n'
    print('Looking up student->'+student+' in Canvas')
    try:
      user = canvas.get_user(student,'sis_login_id')
    except CanvasException as g:
      if str(g) == "Not Found":
        print('Cannot find user login_id->'+ student)
        msgbody+='<b>Canvas cannot find user login_id->'+ student + ', might be a new student who is not in Canvas yet</b>\n'
        logging.info('Cannot find user login_id->'+ student)
    else:
      try:
        n = group.remove_user(user.id)
      except CanvasException as e:
        if str(e) == "Not Found":
            print('User not in group CanvasID->' + str(user.id) + ' login_id->'+ str(student))
            msgbody += 'User not in group CanvasID->' + str(user.id) + ' login_id->'+ str(student) + '\n'
            logging.info('Some sort of exception happened when removing student->'+str(student)+' from Group')
      print('Removed Student->'+str(student)+' from Canvas group')
      msgbody += 'Removed Student->'+str(student)+' from Canvas group' + '\n'
      logging.info('Removed Student->'+str(student)+' from Canvas group')
  # Now add students to group
  for student in studentstoadd:
    msgbody += 'going to try to add '+ str(student) + ' to group ' + str(CanvasGroupID) + '\n'
    try:
      user = canvas.get_user(str(student),'sis_login_id')
    except CanvasException as f:
      if str(f) == "Not Found":
        print('Cannot find user id->'+str(student))
        msgbody += '<b>Cannot find user id->'+str(student) + ' might be a new student who is not in Canvas yet</b>\n'
        logging.info('Cannot find user id!')
    else:    
      try:
        n = group.create_membership(user.id)
      except CanvasException as e:
        if str(e) == "Not Found":
          print('User not in group')
      print('Added Student id->'+str(student)+' to Canvas group->' + str(CanvasGroupID))
      msgbody += 'Added Student id->'+str(student)+' to Canvas group->' + str(CanvasGroupID) + '\n'
      logging.info('Added Student id->'+str(student)+' to Canvas group->' + str(CanvasGroupID))
msgbody+='Done!'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
print('Done!!!')
