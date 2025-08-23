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
from collections.abc import Iterable

'''
This script was originally written to put students into a Canvas "Group" with the counselor. 
However, Canvas Groups seem to not really work well and seem to be deprecated. So now we are using
a Canvas class for each counselor and putting students into the class section for the counselor.

2025 by Eric Dannewitz

'''

    
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
thelogger.info('Canvas Groups for Counselors->Loaded config file and logfile started for AUHSD Counseling Canvas')
thelogger.info('Canvas Groups for Counselors->Loading Counseling CSV file')
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
#Canvas_API_URL = configs['CanvasBETAAPIURL']
Canvas_API_URL = configs['CanvasAPIURL']
#----------------------------------------

Canvas_API_KEY = configs['CanvasAPIKey']
thelogger.info('Canvas Groups for Counselors->Connecting to Canvas')
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
# Go through the counseling list, then add or remove students from groups
msgbody += 'Starting Canvas Counselor Groups for AUHSD Script\n'
for i in CounselorCanvasSection.index:
  CounselorEmail = CounselorCanvasSection['email'][i]
  GradeToGet = CounselorCanvasSection['Grade'][i]
  SchoolSite = CounselorCanvasSection['Site'][i]
  print('Processing info for ' + str(CounselorEmail) + ' Grade->' + str(GradeToGet))
  CanvasSectionID = CounselorCanvasSection['CanvasSectionID'][i]
  msgbody += 'Matching for ' + CounselorEmail + ' - Counselor->' + str(CounselorEmail) + ' - Grade->' + str(GradeToGet) + ' - Canvas Group ID->' + str(CanvasSectionID) + '\n'
  the_query = f"""
  SELECT
    ALTSCH.ALTSC,
    STU.LN,
    STU.ID,
    STU.SEM,
    STU.GR,
    STU.CU,
    TCH.EM
  FROM
    STU
  INNER JOIN
    TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN
  INNER JOIN
    ALTSCH ON STU.SC = ALTSCH.SCID
  WHERE
    (STU.SC < 5)
    AND STU.DEL = 0
    AND ALTSC = '{SchoolSite}'
    AND STU.TG = ''
    AND STU.SP <> '2'
    AND STU.CU > 0
    AND EM = '{CounselorEmail}'
    AND GR = '{GradeToGet}'
  """
  aeriesSQLData = pd.read_sql_query(the_query,engine)
  thelogger.info('Canvas Groups for Counselors->Making SET of Aeries IDs')
  # Now go get the group off Canvas
  msgbody += 'Getting exisiting users from group id->' + str(CanvasSectionID) + '\n'
  # Used to DELETE students from course and sections
  course = canvas.get_course(CounselorCanvasSection['CanvasMainCourseID'][i])
  MainCourseEnrollments = course.get_enrollments(type='StudentEnrollment')
  # used to get students in a section
  section = canvas.get_section(CounselorCanvasSection['CanvasSectionID'][i],include=["students"])
  # make a dataframe that has Student SIS IDs in it
  canvasdf = pd.DataFrame(columns=['ID'])
  print(f"Section looking at -> {section}")
  print(f"CanvasSectionID-> {CounselorCanvasSection['CanvasSectionID'][i]}")
  # get sis_user_id's out of Canvas data
  # comment out if loading NEW Counselors
  #for s in section.students:
  #  tempDF = pd.DataFrame([{'ID': s['sis_user_id']}])
  #  canvasdf = pd.concat([canvasdf,tempDF], axis=0, ignore_index=True)
  print("here")
  # End of new Counselor section
  # add STU_ to AERIES data
  aeriesSQLData['ID'] = 'STU_' + aeriesSQLData['ID'].astype(str)
  studentsinaeriesnotincanvas = aeriesSQLData['ID'][~aeriesSQLData['ID'].isin(canvasdf['ID'])].unique()
  studentsincanvasnotinaeries = canvasdf['ID'][~canvasdf['ID'].isin(aeriesSQLData['ID'])].unique()
  print('Students in Aeries not in Canvas')
  print(studentsinaeriesnotincanvas)
  print('Students in Canvas not in AERIES')
  print(studentsincanvasnotinaeries)
  for student in studentsincanvasnotinaeries:
    thelogger.info('Canvas Groups for Counselors->Looking up student->'+str(student)+' in Canvas')
    msgbody += 'Looking up student->'+str(student)+' in Canvas to delete from course' + '\n'
    print('Looking up student->'+str(student)+' in Canvas to delete from course')
    try:
      user = canvas.get_user(str(student),'sis_user_id')
    except CanvasException as g:
      if str(g) == "Not Found":
        print('Cannot find user sis_id->'+str(student))
        msgbody+='<b>Canvas cannot find user sis_id->'+str(student) + ', might be a new student who is not in Canvas yet</b>\n'
        WasThereAnErr = True
        thelogger.info('Canvas Groups for Counselors->Cannot find user sis_id->'+str(student))
    else:
      lookfordelete = False
      try:
        for stu in MainCourseEnrollments:
                # You have to loop through all the enrollments for the class and then find the student id in the enrollment then tell it to delete it.
          if stu.user_id == user.id:
            lookfordelete = True
            stu.deactivate(task="delete")
            print('Deleted student ->'+str(user.id) + ' from course')
            msgbody += 'Deleted student ->'+str(user.id) + ' from course' + '\n'
            thelogger.info('Deleted student ->'+str(user.id) + ' from course')
      except CanvasException as e:
        if str(e) == "Not Found":
            print('User not in group CanvasID->' + str(user.id) + ' sis_id->'+ str(student))
            msgbody += 'User not in group CanvasID->' + str(user.id) + ' sis_id->'+ str(student) + '\n'
            thelogger.info('Canvas Groups for Counselors->Some sort of exception happened when removing student->'+str(student)+' from Group')
      print('Removed Student->'+str(student)+' from Canvas group')
      msgbody += 'Removed Student->'+str(student)+' from Canvas group' + '\n'
      thelogger.info('Canvas Groups for Counselors->Removed Student->'+str(student)+' from Canvas group')
  # Now add students to group
  # Get the course then loop adding students
  SectionToAddTo = canvas.get_section(CounselorCanvasSection['CanvasSectionID'][i])
  for student in studentsinaeriesnotincanvas:
    print(student)
    try:
      user = canvas.get_user(str(student),'sis_user_id')
      msgbody += 'going to try to add '+ str(student) + ' to section ' + str(SectionToAddTo) + '\n'    
      print(course)
      print(SectionToAddTo.id)
      print(user)
      course.enroll_user(
                        user,
                        enrollment_type = "StudentEnrollment",
                        enrollment={'course_section_id': SectionToAddTo.id,'enrollment_state': 'active','limit_privileges_to_course_section': True}
                      )
      print('Added Student id->'+str(student)+' to Canvas group->' + str(CanvasSectionID))
      msgbody += 'Added Student id->'+str(student)+' to Canvas group->' + str(CanvasSectionID) + '\n'
      thelogger.info('Canvas Groups for Counselors->Added Student id->'+str(student)+' to Canvas group->' + str(CanvasSectionID))
    except CanvasException as ef:
      if str(ef) == "Not Found":
        print('User in AERIES not in Canvas yet sis_id->'+ str(student))
        msgbody += 'User in AERIES not in Canvas yet sis_id-> sis_id->'+ str(student) + '\n'
        thelogger.info('Canvas Groups for Counselors->User in AERIES not in Canvas yet sis_id->'+str(student))
thelogger.info('Canvas Groups for Counselors->Closed AERIES connection')
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
thelogger.info('Canvas Groups for Counselors->Sent Status Message')
thelogger.info('Canvas Groups for Counselors->Done!' + str(end_of_timer - start_of_timer))
print('Done!!!')
