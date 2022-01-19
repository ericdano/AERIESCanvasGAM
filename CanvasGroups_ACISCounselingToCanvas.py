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


#Set up Counselors to pull from Aeries
counselors = [ ('acis','feinberg',10831)]


canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
group = canvas.get_group(10831,include=['users'])
dataframe2 = pd.DataFrame(group.users,columns=['id','name','login_id'])
print(dataframe2)
conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor = conn.cursor()
print('All Students for Counselor')
dataframe1 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
#for EM, SEM in sql_query.groupby('EM'):
#    print(SEM)
dataframe1.to_csv('AllAeries.csv')
dataframe2.to_csv('AllCanvas.csv')
dataframe3=dataframe1
#common = dataframe1.merge(dataframe2,left_on='SEM',right_on='login_id', how='inner')
#print('Difference---------')
#print(common)
dataframe1[~(dataframe1['SEM'].isin(dataframe2['login_id']))]
print('New diff')
print(dataframe1)
print('New Diff 2')
dataframe2[~(dataframe2['login_id'].isin(dataframe3['SEM']))]
print(dataframe2)
#sql_query[(~sql_query.SEM.isin(common.SEM))&(sql_query.login_id.isin(common.login_id))]
#print(sql_query)
conn2 = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
#cursor2 = conn.cursor()
#print('Students by Grade for Counselor')
#sql_query2 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
#for EM, SEM in sql_query2.groupby(['EM','GR']):
    #print(SEM)





#df = pd.DataFrame(group.users,columns=['id','name','login_id'])
#print('Students from Aeries')
#print(students)
#print('Students in Canvas Group')
#print(df)
#students = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
#students.drop(students.columns.difference(['EM']),axis=1,inplace=True)
#students = students.rename(columns={'EM':'login_id'})
# Add user to Canvas Group
#for index, student in students.iterrows():
#    user = canvas.get_user(student["SEM"],'sis_login_id')
#    m = group.create_membership(user.id)
#    print('Created user in group')
#    print(user)
