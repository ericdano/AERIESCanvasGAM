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
Script to update the ACIS counselor Google Group
"""

if __name__ == '__main__':
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    #prep status (msg) email
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    thelogger.info('UpdateACISCounselingListsInGoogle->Loaded config file and logfile started')
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['SendInfoEmailAddr']
    msgbody = ''
    WasThereAnError = False
    DontDeleteFiles = False
    # Change directory to a TEMP Directory where GAM and Python can process CSV files 
    os.chdir('E:\\PythonTemp')
    #populate a table with counselor parts
    counselors = [ ('acis','feinberg')]

    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
    #connection_string = "DRIVER={SQL Server};SERVER=SATURN;DATABASE=DST22000AUHSD;Trusted_Connection=yes"
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    with engine.begin() as connection:
        thelogger.info('UpdateACISCounselingListsInGoogle->Connecting to AERIES to get ACIS ALL student emails')
        sql_query = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',connection)
        sql_query2 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC = 6) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',connection)
        thelogger.info('UpdateACISCounselingListsInGoogle->AERIES connection closed')
    for EM, SEM in sql_query.groupby('EM'):
        filename = str(EM).replace("@auhsdschools.org","")+"ALL.csv"
        filename = filename[1:]
        header = ["SEM"]
        SEM.to_csv(filename, index = False, header = False, columns = header)
    gam.initializeLogging()
    for EM, SEM in sql_query2.groupby(['EM','GR']):
        filename2 = str(EM).replace("(\'","").replace("@","").replace("\',","").replace(".org ","").replace(")","")+".csv"
        filename2 = filename2[1:]
        header = ["SEM"]
        SEM.to_csv(filename2, index = False, header = False, columns = header)
    # Now call gam
    for counselor in counselors:
        # Sync Lists for All Students for counselor
        tempstr1 = counselor[0] + counselor[1] + 'counselinglist'
        tempstr2 = counselor[1] + 'ALL.csv'
        thelogger.info('UpdateACISCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateACISCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            os.remove(tempstr2)
        msgbody += 'Synced ' + counselor[1] + ' All list. Gam Status->' + str(stat1) + '\n' 
        # Sync Lists for Grade 9 for counselor
        tempstr1 = counselor[0] + counselor[1] + 'grade9counselinglist'
        tempstr2 = counselor[1] + 'auhsdschools9.csv'
        thelogger.info('UpdateACISCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateACISCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            os.remove(tempstr2)
        msgbody += 'Synced ' + counselor[1] + ' 9th grade list. Gam Status->' + str(stat1) + '\n' 
        # Sync Lists for Grade 10 for counselor
        tempstr1 = counselor[0] + counselor[1] + "grade10counselinglist"
        tempstr2 = counselor[1] + "auhsdschools10.csv"
        thelogger.info('UpdateACISCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateACISCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            os.remove(tempstr2)
        msgbody += 'Synced ' + counselor[1] + ' 10th grade list. Gam Status->' + str(stat1) + '\n' 
        # Sync Lists for Grade 11 for counselor
        tempstr1 = counselor[0] + counselor[1] + 'grade11counselinglist'
        tempstr2 = counselor[1] + 'auhsdschools11.csv'
        thelogger.info('UpdateACISCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateACISCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            os.remove(tempstr2)
        msgbody += 'Synced ' + counselor[1] + ' 11th grade list. Gam Status->' + str(stat1) + '\n' 
        # Sync Lists for Grade 12 for counselor
        tempstr1 = counselor[0] + counselor[1] + 'grade12counselinglist'
        tempstr2 = counselor[1] + 'auhsdschools12.csv'
        thelogger.info('UpdateACISCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
        stat1 = gam.CallGAMCommand(['gam','update', 'group', tempstr1, 'sync', 'members', 'file', tempstr2])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateACISCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            os.remove(tempstr2)
        msgbody += 'Synced ' + counselor[1] + ' 12th grade list. Gam Status->' + str(stat1) + '\n' 
    msgbody+='Done!'
    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AUHSD ACIS Counseling Lists to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD ACIS Counseling Lists to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    thelogger.info('UpdateACISCounselingListsInGoogle->Sent Status message')
    thelogger.info('UpdateACISCounselingListsInGoogle->Done!! - Took ' + str(end_of_timer - start_of_timer))
    print('Done!!!')
