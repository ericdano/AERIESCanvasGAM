import pandas as pd
import os, sys, pyodbc, shlex, subprocess, gam, datetime, json, smtplib
from pathlib import Path
import glob
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
#prep status (msg) email
msg = EmailMessage()
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
WasThereAnError = False
# Change directory to a TEMP Directory where GAM and Python can process CSV files 
os.chdir('E:\\PythonTemp')
#populate a table with counselor parts
counselors = [ ('acis','feinberg')]

conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor = conn.cursor()
sql_query1 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.PEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 AND STU.GR < 12 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
conn.close()
sql_query1.drop(sql_query1.columns.difference(['SEM',
                                              'PEM']), axis=1,inplace=True)
c_name = ["email"]
listylist = pd.DataFrame(columns = c_name)
for index, row in sql_query1.iterrows():
    listylist = listylist.append({'email':row['SEM']},ignore_index=True)
    listylist = listylist.append({'email':row['PEM']},ignore_index=True)
header = ["email"]
listylist.to_csv('acisstudentparents.csv',index = False, header = False, columns = header)
stat1 = gam.CallGAMCommand(['gam','update', 'group', 'acisgrades9to11studentsandparents', 'sync', 'members', 'file', 'acisstudentparents.csv'])
if stat1 != 0:
    WasThereAnError = True
os.remove('acisstudentparents.csv')
msgbody += 'Synced ACIS Student Parent list. Gam Status->' + str(stat1) + '\n' 
msgbody+='Done!'
if WasThereAnError:
    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AUHSD ACIS Grades 9 to 11 Student and Parents to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
else:
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD ACIS Grades 9 to 11 Student and Parents to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
end_of_timer = timer()
msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
print('Done!!!')
