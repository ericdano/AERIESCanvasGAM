import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json, logging, smtplib, datetime
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
CounselorCSV = Path.home() / ".Acalanes" / "CanvasCounselingGroups.csv"
logfilename = Path.home() / ".Acalanes" / configs['logfilename']
logging.basicConfig(filename=str(logfilename), level=logging.INFO)
logging.info('Loaded config file and logfile started')
logging.info('Loading Counseling CSV file')
#prep status (msg) and debug (dmsg) emails
msg = EmailMessage()
msg['Subject'] = str(configs['SMTPStatusMessage'] + " " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
# The counseling CSV has counselors email address, there sis_id, canvas group and grade
# Grade can have a field All in it that it will then place into a All students
# at site group for the counselor
CounselorCanvasGroups = pd.read_csv(CounselorCSV)

conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
#
cursor = conn.cursor()
#-----Canvas Info
Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
logging.info('Connecting to Canvas')
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)

account = canvas.get_account(1)
# Go through the counseling list, then add or remove students from groups
msgbody += 'Starting Canvas Counseler Groups Script\n'
for i in CounselorCanvasGroups.index:
  CounselorEmail = CounselorCanvasGroups['email'][i]
  CounselorSISID = CounselorCanvasGroups['SISID'][i]
  GradeToGet = CounselorCanvasGroups['Grade'][i]
  CanvasGroupID = CounselorCanvasGroups['CanvasGroupID'][i]
  msgbody += 'Matching for ' + CounselorEmail + ' - ' + str(CounselorSISID) + ' - ' + str(GradeToGet) + ' - ' + str(CanvasGroupID) + '\n'
  if (GradeToGet == str('All')):
    dataframe1 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.ID, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 AND EM = \'' + CounselorEmail + '\'',conn)
  else:
    dataframe1 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.ID, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 AND EM = \'' + CounselorEmail + '\' AND GR = \'' + GradeToGet + '\'',conn)
  #print('Matching for ' + CounselorEmail + ' Grade ' + str(GradeToGet) + ' CanvasGroupID ' + str(CanvasGroupID))
  #print(sql_query)
  logging.info('Making SET of Aeries IDs')
  aerieslist = set(dataframe1.ID)
  # Now go get the group off Canvas
  msgbody += 'Getting exisiting users from group id->' + str(CanvasGroupID) + '\n'
  group = canvas.get_group(CanvasGroupID,include=['users'])
  dataframe2 = pd.DataFrame(group.users,columns=['sis_user_id'])
  canvaslist = set(pd.to_numeric(dataframe2.sis_user_id))
#  print('Canvas')
#  print(canvaslist)
  #Subtract items from the Aeries set that are in the Canvas set
  #The resulting set is the SIS_IDs we need to ADD to the Group
  studentstoadd = aerieslist - canvaslist
  #Subtract items from Canvaslist set that are in Aeries set. 
  #These are students that need to be removed from the group
  studentstoremove = canvaslist - aerieslist
  #Keep the teacher in the group though, so take them OUT of the set
  studentstoremove.remove(CounselorSISID) # Keep teacher in canvas group
#  print('Students to add')
#  print(studentstoadd)
#  print('Students to remove')
#  print(studentstoremove)
  for student in studentstoremove:
    logging.info('Looking up student->'+str(student)+' in Canvas')
    msgbody += 'Looking up student->'+str(student)+' in Canvas'
    try:
      user = canvas.get_user(str(student),'sis_user_id')
    except CanvasException as g:
      if str(g) == "Not Found":
        print('Cannot find user sis_id->'+str(student))
        logging.info('Cannot find user sis_id->'+str(student))
    try:
      n = group.remove_user(user.id)
    except CanvasException as e:
      if str(e) == "Not Found":
          print('User not in group')
          logging.info('Some sort of exception happened when removing student->'+str(student)+' from Group')
    msgbody += 'Removed Student->'+str(student)+' from Canvas group' + '\n'
    logging.info('Removed Student->'+str(student)+' from Canvas group')
# Now add students to group
  for student in studentstoadd:
    msgbody += 'going to try to add '+ str(student) + ' to group ' + CanvasGroupID + '\n'
    try:
      user = canvas.get_user(str(student),'sis_user_id')
    except CanvasException as f:
      if str(f) == "Not Found":
        print('Cannot find user id->'+str(student))
        logging.info('Cannot find user id!')
    try:
      n = group.create_membership(user.id)
    except CanvasException as e:
      if str(e) == "Not Found":
        print('User not in group')
    msgbody += 'Added Student id->'+str(student)+' to Canvas group' + CanvasGroupID + '\n'
    logging.info('Added Student id->'+str(student)+' to Canvas group')
msgbody+='Done!'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
# Main part where we create the BIG group of ALL students a counselor has, and then put them into a Group
#
#group = canvas.get_group(10835,include=['users'])
#print(students)
#print(counselors[11])
##print(counselors[11][3])
#for index, student in students.iterrows():
#    if student["EM"] == counselors[11][2]:
#        user = canvas.get_user(student["SEM"],'sis_login_id')
#        m = group.create_membership(user.id)
#        print('Created user in group')
#        print(user)