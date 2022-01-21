import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging
os.chdir('E:\\PythonTemp')
counselors = [ ('ahs','todd','ctodd@auhsdschools.org',''),
                ('ahs','meadows'),
                ('ahs','schonauer'),
                ('ahs','martin'),
                ('chs','turner'),
                ('chs','dhaliwal'),
                ('chs','santellan'),
                ('chs','magno'),
                ('llhs','wright'),
                ('llhs','feinberg'),
                ('llhs','constantin'),
                ('llhs','bloodgood'),
                ('llhs','sabeh'),
                ('mhs','vasquez'),
                ('mhs','conners'),
                ('mhs','watson'),
                ('mhs','vasicek') ]
conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
#
cursor = conn.cursor()
sql_query = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.ID, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)

for EM, SEM in sql_query.groupby('EM'):
    filename = str(EM).replace("@auhsdschools.org","")+"ALL.csv"
    filename = filename[1:]
    header = ["SEM"]
    SEM.to_csv(filename, index = False, header = False, columns = header)

for EM, SEM in sql_query.groupby(['EM','GR']):
    filename2 = str(EM).replace("(\'","").replace("@","").replace("\',","").replace(".org ","").replace(")","")+".csv"
    filename2 = filename2[1:]
    header = ["SEM"]
    SEM.to_csv(filename2, index = False, header = False, columns = header)

#-----Canvas Info()
Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
# Main part where we create the BIG group of ALL students a counselor has, and then put them into a Group
#
#canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
#account = canvas.get_account(1)
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