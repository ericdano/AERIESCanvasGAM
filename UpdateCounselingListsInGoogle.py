import pandas as pd
import os, sys, pyodbc, shlex, subprocess, gam, datetime, json, smtplib
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
#This script finds counselors and their assigned students in AERIES, then updates Google Group Annouce only lists with any student changes

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
counselors = [ ('ahs','todd'),
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
cursor = conn.cursor()
sql_query = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
for EM, SEM in sql_query.groupby('EM'):
    filename = str(EM).replace("@auhsdschools.org","")+"ALL.csv"
    filename = filename[1:]
    header = ["SEM"]
    SEM.to_csv(filename, index = False, header = False, columns = header)
conn.close()
conn2 = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor2 = conn2.cursor()
sql_query2 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn2)
for EM, SEM in sql_query2.groupby(['EM','GR']):
    filename2 = str(EM).replace("(\'","").replace("@","").replace("\',","").replace(".org ","").replace(")","")+".csv"
    filename2 = filename2[1:]
    header = ["SEM"]
    SEM.to_csv(filename2, index = False, header = False, columns = header)
conn2.close()
# Now call gam
for counselor in counselors:
    # Sync Lists for All Students for counselor
    tempstr1 = counselor[0] + counselor[1] + 'counselinglist'
    tempstr2 = counselor[1] + 'ALL.csv'
    stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
    if stat1 != 0:
        WasThereAnError = True
    os.remove(tempstr2)
    msgbody += 'Synced ' + counselor[1] + ' All list. Gam Status->' + str(stat1) + '\n' 
    # Sync Lists for Grade 9 for counselor
    tempstr1 = counselor[0] + counselor[1] + 'grade9counselinglist'
    tempstr2 = counselor[1] + 'auhsdschools9.csv'
    stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
    if stat1 != 0:
        WasThereAnError = True
    os.remove(tempstr2)
    msgbody += 'Synced ' + counselor[1] + ' 9th grade list. Gam Status->' + str(stat1) + '\n' 
    # Sync Lists for Grade 10 for counselor
    tempstr1 = counselor[0] + counselor[1] + "grade10counselinglist"
    tempstr2 = counselor[1] + "auhsdschools10.csv"
    stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
    if stat1 != 0:
        WasThereAnError = True
    os.remove(tempstr2)
    msgbody += 'Synced ' + counselor[1] + ' 10th grade list. Gam Status->' + str(stat1) + '\n' 
    # Sync Lists for Grade 11 for counselor
    tempstr1 = counselor[0] + counselor[1] + 'grade11counselinglist'
    tempstr2 = counselor[1] + 'auhsdschools11.csv'
    stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
    if stat1 != 0:
        WasThereAnError = True
    os.remove(tempstr2)
    msgbody += 'Synced ' + counselor[1] + ' 11th grade list. Gam Status->' + str(stat1) + '\n' 
    # Sync Lists for Grade 12 for counselor
    tempstr1 = counselor[0] + counselor[1] + 'grade12counselinglist'
    tempstr2 = counselor[1] + 'auhsdschools12.csv'
    stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
    if stat1 != 0:
        WasThereAnError = True
    os.remove(tempstr2)
    msgbody += 'Synced ' + counselor[1] + ' 12th grade list. Gam Status->' + str(stat1) + '\n' 
if WasThereAnError:
    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AUHSD ACIS Counseling Lists to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
else:
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD ACIS Counseling Lists to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
end_of_timer = timer()
msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
print('Done!!!')
