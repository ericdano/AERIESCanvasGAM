import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging
#-----Canvas Info
Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']


#Set up Counselors to pull from Aeries along with the Canvas groups they are part of
counselors = [ ('acis','feinberg',10831)]


canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
group = canvas.get_group(10831,include=['users'])
testuser=canvas.get_user(3772)
print(testuser.sis_user_id)

dataframe2 = pd.DataFrame(group.users,columns=['login_id'])
conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor = conn.cursor()
#print('All Students for Counselor')
dataframe1 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
aerieslist = set(dataframe1.SEM)
canvaslist = set(dataframe2.login_id)
studentstoadd = aerieslist - canvaslist
studentstoremove = canvaslist - aerieslist
studentstoremove.remove('sfeinberg@auhsdschools.org') # Keep teacher in canvas group
studentstoremove.remove('edannewitz@auhsdschools.org')
for student in studentstoremove:
  try:
    user = account.get_users(search_term=str(student))
  except CanvasException as g:
    if str(g) == "Not Found":
      print('Error finding user!')
#  user = canvas.get_user(str(student),'sis_login_id')
  try:
    n = group.remove_user(user[0].id)
  except CanvasException as e:
    if str(e) == "Not Found":
        print('User not in group')
  print('Removed Student->'+str(student)+' from Canvas group')
print(studentstoadd)
# Now add students to group
for student in studentstoadd:
  print('going to try to add'+str(student))
  try:
#    user = canvas.get_user(str(student),'sis_login_id')
    user = account.get_users(search_term=str(student))
  except CanvasException as f:
    if str(f) == "Not Found":
      print('Cannot find user->'+str(student))
  try:
    n = group.create_membership(user[0].id)
  except CanvasException as e:
    if str(e) == "Not Found":
      print('User not in group')
  print('Added Student->'+str(student)+' to Canvas group')
  print(user[0].sis_user_id)
  print(user[0].id)
# Add user to Canvas Group
#for index, student in students.iterrows():
#    user = canvas.get_user(student["SEM"],'sis_login_id')
#    m = group.create_membership(user.id)
#    print('Created user in group')
#    print(user)
