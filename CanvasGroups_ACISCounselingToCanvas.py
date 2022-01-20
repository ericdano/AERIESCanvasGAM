import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json, logging
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging
logfilename = Path.home() / ".Acalanes" / configs['logfilename']
logging.basicConfig(filename=str(logfilename), level=logging.INFO)
logging.info('Loaded config file and logfile started')
#-----Canvas Info
Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
logging.info('Connecting to Canvas')
account = canvas.get_account(1)
#Set up Counselors to pull from Aeries along with the Canvas groups they are part of
# School, Counselor lastname, the Canvas Group ID
counselors = [ ('acis','feinberg',10831)]

conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor = conn.cursor()
logging.info('Getting data from AERIES')
dataframe1 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.ID, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
#Now make a set of JUST the SIS_USER_IDs from Aeries
logging.info('Making SET of Aeries IDs')
aerieslist = set(dataframe1.ID)

#Get Exisiting users SIS_USER_ID from Counseling Group
logging.info('')
group = canvas.get_group(10831,include=['users'])
dataframe2 = pd.DataFrame(group.users,columns=['sis_user_id'])
#Make a set of JUST SIS_USER_IDs that are currently in the Canvas Group
canvaslist = set(dataframe2.sis_user_id)
#Subtract items from the Aeries set that are in the Canvas set
#The resulting set is the SIS_IDs we need to ADD to the Group
studentstoadd = aerieslist - canvaslist
#Subtract items from Canvaslist set that are in Aeries set. 
#These are students that need to be removed from the group
studentstoremove = canvaslist - aerieslist
#Keep the teacher in the group though, so take them OUT of the set
studentstoremove.remove('sfeinberg@auhsdschools.org') # Keep teacher in canvas group
studentstoremove.remove('edannewitz@auhsdschools.org')
for student in studentstoremove:
  logging.info('Looking up student->'+str(student)+' in Canvas')
  try:
    user = canvas.get_user(str(student))
  except CanvasException as g:
    if str(g) == "Not Found":
      print('Cannot find user id->'+str(student))
      logging.info('Cannot find user id->'+str(student))
  try:
    n = group.remove_user(user.sis_user_id)
  except CanvasException as e:
    if str(e) == "Not Found":
        print('User not in group')
        logging.info('Some sort of exception happened when removing student->'+str(student)+' from Group')
  print('Removed Student->'+str(student)+' from Canvas group')
  logging.info('Removed Student->'+str(student)+' from Canvas group')
# Now add students to group
for student in studentstoadd:
  print('going to try to add'+str(student))
  try:
    user = canvas.get_user(str(student))
  except CanvasException as f:
    if str(f) == "Not Found":
      print('Cannot find user id->'+str(student))
  try:
    n = group.create_membership(user.sis_user_id)
  except CanvasException as e:
    if str(e) == "Not Found":
      print('User not in group')
  print('Added Student id->'+str(student)+' to Canvas group')
  logging.info('Added Student id->'+str(student)+' to Canvas group')
