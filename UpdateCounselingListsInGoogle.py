import pandas as pd
import os, sys, shlex, subprocess, gam, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

"""
This script finds counselors and their assigned students in AERIES, then updates Google Groups lists with any student changes
Counselors are the Owners of the list. The GAM commands updates the groups with whatever is in the CSV file
"""
def GetAERIESData(thelogger):
    os.chdir('E:\\PythonTemp')
    """
     pyodbc is depriciated in Pandas 1.5 moved to Sqlalchemy
    conn = pyodbc.connect('Driver={SQL Server};'
                        'Server=SATURN;'
                        'Database=DST22000AUHSD;'
                        'Trusted_Connection=yes;')
    cursor = conn.cursor()
    """
    thelogger.info('UpdateCounselingListsInGoogle->Connecting To AERIES to get ALL students for Counselors')
    connection_string = "DRIVER={SQL Server};SERVER=SATURN;DATABASE=DST22000AUHSD;Trusted_Connection=yes"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    sql_query = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',engine)
    for EM, SEM in sql_query.groupby('EM'):
        filename = str(EM).replace("@auhsdschools.org","")+"ALL.csv"
        filename = filename[1:]
        header = ["SEM"]
        SEM.to_csv(filename, index = False, header = False, columns = header)
    thelogger.info('UpdateCounselingListsInGoogle->Closed AERIES connection')
    """
     pyodbc is depriciated in Pandas 1.5 moved to Sqlalchemy
    conn = pyodbc.connect('Driver={SQL Server};'
                        'Server=SATURN;'
                        'Database=DST22000AUHSD;'
                        'Trusted_Connection=yes;')
    cursor = conn.cursor()
    """
    thelogger.info('UpdateCounselingListsInGoogle->Connecting To AERIES to get students for Counselors by grade level')
    sql_query2 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',engine)
    for EM, SEM in sql_query2.groupby(['EM','GR']):
        filename2 = str(EM).replace("(\'","").replace("@","").replace("\',","").replace(".org ","").replace(")","")+".csv"
        filename2 = filename2[1:]
        header = ["SEM"]
        SEM.to_csv(filename2, index = False, header = False, columns = header)
    #conn2.close()
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
    counselors = [ ('ahs','castillo-gallardo'),
                    ('ahs','meadows'),
                    ('ahs','schonauer'),
                    ('ahs','martin'),
                    ('chs','thayer'),
                    ('chs','dhaliwal'),
                    ('chs','santellan'),
                    ('chs','magno'),
                    ('llhs','medrano'),
                    ('llhs','feinberg'),
                    ('llhs','constantin'),
                    ('llhs','bloodgood'),
                    ('llhs','sabeh'),
                    ('mhs','vasquez'),
                    ('mhs','conners'),
                    ('mhs','zielinski'),
                    ('mhs','shawn') ]
    GetAERIESData(thelogger)
    gam.initializeLogging()
    # Now call gam
    for counselor in counselors:
        # Sync Lists for All Students for counselor
        tempstr1 = counselor[0] + counselor[1] + 'counselinglist'
        tempstr2 = counselor[1] + 'ALL.csv'
        thelogger.info('UpdateCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        try:
            os.remove(tempstr2)
        except:
            msgbody += 'Error removing ' + counselor[1] + ' ALL grades list.\n' 
            thelogger.critical('UpdateCounselingListsInGoogle->Error trying to remove file ' + counselor[1] + ' ALL Grades list csv')
        msgbody += 'Synced ' + counselor[1] + ' All list. Gam Status->' + str(stat1) + '\n' 
        # Sync Lists for Grade 9 for counselor
        tempstr1 = counselor[0] + counselor[1] + 'grade9counselinglist'
        tempstr2 = counselor[1] + 'auhsdschools9.csv'
        thelogger.info('UpdateCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        try:
            os.remove(tempstr2)
        except:
            msgbody += 'Error removing ' + counselor[1] + ' 9th grade list.\n' 
            thelogger.critical('UpdateCounselingListsInGoogle->Error trying to remove file ' + counselor[1] + ' 9th grade list csv')
        msgbody += 'Synced ' + counselor[1] + ' 9th grade list. Gam Status->' + str(stat1) + '\n' 
        # Sync Lists for Grade 10 for counselor
        tempstr1 = counselor[0] + counselor[1] + "grade10counselinglist"
        tempstr2 = counselor[1] + "auhsdschools10.csv"
        thelogger.info('UpdateCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        try:
            os.remove(tempstr2)
        except:
            msgbody += 'Error removing ' + counselor[1] + ' 10th grade list.\n' 
            thelogger.critical('UpdateCounselingListsInGoogle->Error trying to remove file ' + counselor[1] + ' 10th grade list csv')
        msgbody += 'Synced ' + counselor[1] + ' 10th grade list. Gam Status->' + str(stat1) + '\n' 
        # Sync Lists for Grade 11 for counselor
        tempstr1 = counselor[0] + counselor[1] + 'grade11counselinglist'
        tempstr2 = counselor[1] + 'auhsdschools11.csv'
        thelogger.info('UpdateCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        try:
            os.remove(tempstr2)
        except:
            msgbody += 'Error removing ' + counselor[1] + ' 11th grade list.\n' 
            thelogger.critical('UpdateCounselingListsInGoogle->Error trying to remove file ' + counselor[1] + ' 11th grade list csv')
        msgbody += 'Synced ' + counselor[1] + ' 11th grade list. Gam Status->' + str(stat1) + '\n' 
        # Sync Lists for Grade 12 for counselor
        tempstr1 = counselor[0] + counselor[1] + 'grade12counselinglist'
        tempstr2 = counselor[1] + 'auhsdschools12.csv'
        thelogger.info('UpdateCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        try:
            os.remove(tempstr2)
        except:
            msgbody += 'Error removing ' + counselor[1] + ' 12th grade list.\n' 
            thelogger.critical('UpdateCounselingListsInGoogle->Error trying to remove file ' + counselor[1] + ' 12th grade list csv')
        msgbody += 'Synced ' + counselor[1] + ' 12th grade list. Gam Status->' + str(stat1) + '\n' 
    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AUHSD Counseling Lists to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD Counseling Lists to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    thelogger.info('UpdateCounselingListsInGoogle->Sent status message')
    thelogger.info('UpdateCounselingListsInGoogle->DONE! - took ' + str(end_of_timer - start_of_timer))
    print('Done!!!')

if __name__ == '__main__':
    main()