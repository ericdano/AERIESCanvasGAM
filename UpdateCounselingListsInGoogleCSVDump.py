import pandas as pd
import os, sys, pyodbc, shlex, subprocess, gam, datetime, json, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

#This script finds counselors and their assigned students in AERIES, then updates Google Group Annouce only lists with any student changes

def GetAERIESData(thelogger):
    os.chdir('E:\\PythonTemp')
    conn = pyodbc.connect('Driver={SQL Server};'
                        'Server=SATURN;'
                        'Database=DST22000AUHSD;'
                        'Trusted_Connection=yes;')
    thelogger.info('UpdateCounselingListsInGoogle->Connecting To AERIES to get ALL students for Counselors')
    cursor = conn.cursor()
    sql_query = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
    for EM, SEM in sql_query.groupby('EM'):
        filename = str(EM).replace("@auhsdschools.org","")+"ALL.csv"
        filename = filename[1:]
        header = ["SEM"]
        SEM.to_csv(filename, index = False, header = False, columns = header)
    conn.close()
    thelogger.info('UpdateCounselingListsInGoogle->Closed AERIES connection')
    conn2 = pyodbc.connect('Driver={SQL Server};'
                        'Server=SATURN;'
                        'Database=DST22000AUHSD;'
                        'Trusted_Connection=yes;')
    thelogger.info('UpdateCounselingListsInGoogle->Connecting To AERIES to get students for Counselors by grade level')
    cursor2 = conn2.cursor()
    sql_query2 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn2)
    for EM, SEM in sql_query2.groupby(['EM','GR']):
        filename2 = str(EM).replace("(\'","").replace("@","").replace("\',","").replace(".org ","").replace(")","")+".csv"
        filename2 = filename2[1:]
        header = ["SEM"]
        SEM.to_csv(filename2, index = False, header = False, columns = header)
    conn2.close()
    thelogger.info('UpdateCounselingListsInGoogle->Closed AERIES connection')

def main():
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
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
                    ('chs','thayer'),
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
    GetAERIESData(thelogger)
    print('Done!!!')

if __name__ == '__main__':
    main()