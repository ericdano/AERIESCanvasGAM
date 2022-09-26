import pandas as pd
import os, sys, shlex, subprocess, json, logging, smtplib, datetime, gam
from pathlib import Path
from timeit import default_timer as timer
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

"""
 Updates a Canvas group from a Google Sheet

 The Groups CSV has to have the teacher/staff email address, there login_id, canvas group and grade
 Grade can have a field All in it that it will then place into a All students
 at site group for the counselor
 format of the CSV is 
 StaffEmail, SheetFileID, CanvasGroupID
"""
if __name__ == '__main__':
  start_of_timer = timer()
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  # Logging
  #SheetsToGroupsCSV = Path.home() / ".Acalanes" / "SheetsToCanvasGroups.csv"
  if configs['logserveraddress'] == "":
      logfilename = Path.home() / ".Acalanes" / configs['logfilename']
      thelogger = logging.getLogger('MyLogger')
      thelogger.basicConfig(filename=str(logfilename), level=thelogger.info)
  else:
      thelogger = logging.getLogger('MyLogger')
      thelogger.setLevel(logging.DEBUG)
      handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
      thelogger.addHandler(handler)
  logging.info('CanvasGroups_GoogleSheetToGroup->Loaded config file and logfile started for AUHSD Google Sheets to Canvas')
  logging.info('CanvasGroups_GoogleSheetToGroup->Loading CSV file')
  #prep status (msg) email
  msg = EmailMessage()
  msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD Groups from Sheets To Canvas " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  msg['From'] = configs['SMTPAddressFrom']
  msg['To'] = configs['SendInfoEmailAddr']
  msgbody = ''
  # Pull Master List down from Google
  MasterListID = '1CDj-hq5MkKStZObMi9XKGDrSSvDA_SvJbXUhJkn7_ts'
  SheetsToGroupsCSV = 'e:\PythonTemp\MasterListSheetsToGroups.csv'
  rc2 = gam.CallGAMCommand(['gam','user', 'edannewitz@auhsdschools.org','get','drivefile','id',MasterListID,'format','csv','targetfolder','e:\PythonTemp','targetname','MasterListSheetsToGroups.csv','overwrite','true'])
  if rc2 != 0:
    logging.critical('CanvasGroups_GoogleSheetToGroup->GAM Error getting Google sheet')
  SheetsToGroups = pd.read_csv(SheetsToGroupsCSV)
  os.remove(SheetsToGroupsCSV)
  logging.info('CanvasGroups_GoogleSheetToGroup->Success loding CSV file')
  print('CSV File loaded ok!')
  #-----Canvas Info
  Canvas_API_URL = configs['CanvasAPIURL']
  Canvas_API_KEY = configs['CanvasAPIKey']
  logging.info('CanvasGroups_GoogleSheetToGroup->Connecting to Canvas')
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
    if rc2 != 0:
      logging.critical('CanvasGroups_GoogleSheetToGroup->GAM Error getting Google sheet')
    dataframe1 = pd.read_csv('e:\PythonTemp\SheetforCanvasGroup' + str(CanvasGroupID) + '.csv')
    os.remove('e:\PythonTemp\SheetforCanvasGroup' + str(CanvasGroupID) + '.csv')
    print('Processing info for ' + StaffEmail + ' Group->' + str(CanvasGroupID))
    msgbody += 'Matching for ' + StaffEmail + ' - Canvas Group ID->' + str(CanvasGroupID) + '\n'
    logging.info('CanvasGroups_GoogleSheetToGroup->Making SET of Email Addresses for ' + StaffEmail + '(' + str(CanvasGroupID) + ')')
    print('Making SET of Email Addresses for ' + StaffEmail + '(' + str(CanvasGroupID) + ')')
    SheetList = set(dataframe1.email)
    #print(SheetList)
    # Now go get the group off Canvas
    msgbody += 'Getting exisiting users from ' + StaffEmail + ' group(' + str(CanvasGroupID) + ')\n'
    #print(CanvasGroupID)
    try:
      group = canvas.get_group(CanvasGroupID,include=['users'])
    except CanvasException as f:
      if str(f) == "Not Found":
        print('Error finding Group->' + str(CanvasGroupID))
        logging.critical('CanvasGroups_GoogleSheetToGroup->Error finding Group->' + str(CanvasGroupID) + '(' + StaffEmail + ')')
    #print(group)
    dataframe2 = pd.DataFrame(group.users,columns=['login_id'])
    #print(dataframe2)
    canvaslist = set(dataframe2.login_id)
    #Subtract items from the GoogleSheet set that are in the Canvas set
    #The resulting set are the emails we need to ADD to the Group
    studentstoadd = SheetList - canvaslist
    #Subtract items from Canvaslist set that are in Aeries set. 
    #These are students that need to be removed from the group
    studentstoremove = canvaslist - SheetList
    #Keep the teacher in the group though, so take them OUT of the set
    studentstoremove.remove(StaffEmail) # Keep teacher in canvas group
    #
    for student in studentstoremove:
      logging.info('CanvasGroups_GoogleSheetToGroup->Looking up student->'+student+' in Canvas')
      msgbody += 'Looking up student->'+student+' in Canvas' + '\n'
      print('Looking up student->' + student +' in Canvas')
      try:
        user = canvas.get_user(student,'sis_login_id')
      except CanvasException as g:
        if str(g) == "Not Found":
          print('Cannot find user login_id->'+ student)
          msgbody+='<b>Canvas cannot find user login_id->'+ student + ', might be a new student who is not in Canvas yet</b>\n'
          logging.error('CanvasGroups_GoogleSheetToGroup->Cannot find user login_id->'+ student + + ' might be a new student who is not in Canvas yet')
      else:
        try:
          n = group.remove_user(user.id)
        except CanvasException as e:
          if str(e) == "Not Found":
              print('User not in group CanvasID->' + str(user.id) + ' login_id->'+ student)
              msgbody += 'User not in group CanvasID->' + str(user.id) + ' login_id->'+ student + '\n'
              logging.critical('Some sort of exception happened when removing student->'+ student +' from Group')
        print('Removed Student->'+ student +' from Canvas group')
        msgbody += 'Removed Student->' + student +' from Canvas group' + '\n'
        logging.info('CanvasGroups_GoogleSheetToGroup->Removed Student->'+ student + ' from Canvas group')
    # Now add students to group
    for student in studentstoadd:
      msgbody += 'going to try to add '+ student + ' to group ' + str(CanvasGroupID) + '(' + StaffEmail + ')\n'
      try:
        user = canvas.get_user(student,'sis_login_id')
      except CanvasException as f:
        if str(f) == "Not Found":
          print('Cannot find user id->'+ student)
          msgbody += '<b>Cannot find user id->'+ student + ' might be a new student who is not in Canvas yet</b>\n'
          logging.critical('CanvasGroups_GoogleSheetToGroup->Cannot find user id!')
      else:    
        try:
          n = group.create_membership(user.id)
        except CanvasException as e:
          if str(e) == "Not Found":
            print('User ID adding to membership error')
            logging.critical('User ID adding to membership error')
        print('Added Student id->' + student +' to Canvas group->' + str(CanvasGroupID) + '(' + StaffEmail + ')')
        msgbody += 'Added Student id->' + student +' to Canvas group->' + str(CanvasGroupID) + '(' + StaffEmail + ')\n'
        logging.info('CanvasGroups_GoogleSheetToGroup->Added Student id->'+ student +' to Canvas group->' + str(CanvasGroupID) + '(' + StaffEmail + ')')
  msgbody+='Done!'
  end_of_timer = timer()
  msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
  msg.set_content(msgbody)
  s = smtplib.SMTP(configs['SMTPServerAddress'])
  s.send_message(msg)
  print('Done!!!')
  logging.info('CanvasGroups_GoogleSheetToGroup->Done! - Took '+ str(end_of_timer - start_of_timer))

