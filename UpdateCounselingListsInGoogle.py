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
def GetAERIESData(thelogger,configs):
    os.chdir('E:\\PythonTemp')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    thelogger.info('UpdateCounselingListsInGoogle->Connecting To AERIES to get ALL students for Counselors')
    thequery1 = f"""
    SELECT
        ALTSCH.ALTSC,
        STU.LN,
        STU.SEM,
        STU.GR,
        STU.CU,
        TCH.EM,
        CONCAT(ALTSCH.ALTSC,TCH.EM) AS SITEEM,
        CONCAT(ALTSCH.ALTSC,CAST(STU.GR as VARCHAR),TCH.EM) AS SITEGRADEEM
    FROM STU
    INNER JOIN
        TCH ON STU.SC = TCH.SC AND
        STU.CU = TCH.TN
    INNER JOIN
        ALTSCH ON STU.SC = ALTSCH.SCID
    WHERE
        (STU.SC < 5) AND
        STU.DEL = 0 AND STU.TG = '' AND
        STU.SP <> '2' AND
        STU.CU > 0
    ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN
    """
    sql_query = pd.read_sql_query(thequery1,engine)
    for SITEEM, SEM in sql_query.groupby('SITEEM'):
        filename = SITEEM.replace("@auhsdschools.org","")+"ALL.csv"
        #filename = filename[1:]
        header = ["SEM"]
        SEM.to_csv(filename, index = False, header = False, columns = header)
    thelogger.info('UpdateCounselingListsInGoogle->Closed AERIES connection')
    thequery2 = f"""
    SELECT
        ALTSCH.ALTSC,
        STU.LN,
        STU.SEM,
        STU.GR,
        STU.CU,
        TCH.EM,
        CONCAT(ALTSCH.ALTSC,TCH.EM) AS SITEEM,
        CONCAT(ALTSCH.ALTSC,CAST(STU.GR as VARCHAR),TCH.EM) AS SITEGRADEEM
    FROM
        STU
    INNER JOIN
        TCH ON STU.SC = TCH.SC AND
        STU.CU = TCH.TN
    INNER JOIN
        ALTSCH ON STU.SC = ALTSCH.SCID
    WHERE
        (STU.SC < 5) AND
        STU.DEL = 0 AND
        STU.TG = '' AND
        STU.SP <> '2' AND
        STU.CU > 0
    ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN
    """
    sql_query2 = pd.read_sql_query(thequery2,engine)
    for SITEGRADEEM, SEM in sql_query2.groupby('SITEGRADEEM'):
        filename2 = SITEGRADEEM.replace("@auhsdschools.org","")+".csv"
        #filename2 = filename2[1:]
        header = ["SEM"]
        SEM.to_csv(filename2, index = False, header = False, columns = header)
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
    DontDeleteFiles = False
    # Change directory to a TEMP Directory where GAM and Python can process CSV files 
    os.chdir('E:\\PythonTemp')
    #populate a table with counselor parts
    #populate a table with counselor parts
    counselors = [ ('AHS','evasquez','vasquez'),
                    ('AHS','mmeadows','meadows'),
                    ('AHS','aschonauer','schonauer'),
                    ('AHS','smartin','martin'),
                    ('CHS','ccastillo-gallardo','castillo-gallardo'),
                    ('CHS','adhaliwal','dhaliwal'),
                    ('CHS','csantellan','santellan'),
                    ('CHS','dmagno','magno'),
                    ('LLHS','jennysmith','jennysmith'),
                    ('LLHS','sfeinberg','feinberg'),
                    ('LLHS','mconstantin','constantin'),
                    ('LLHS','kbloodgood','bloodgood'),
                    ('LLHS','msabeh','sabeh'),
                    ('MHS','evasquez','vasquez'),
                    ('MHS','econners','conners'),
                    ('MHS','rzielinski','zielinski'),
                    ('MHS','nganey','ganey')]
    msgbody += f"Using Database->{configs['AERIESDatabase']}\n"
    GetAERIESData(thelogger,configs)
    gam.initializeLogging()
    # Now call gam
    for counselor in counselors:
        # Sync Lists for All Students for counselor
        gamliststring = counselor[0] + counselor[2] + 'counselinglist'
        filenamestring = counselor[0] + counselor[1] + 'ALL.csv'
        thelogger.info(f"UpdateCounselingListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]} ALL grades list.\n" 
                thelogger.critical(f"UpdateCounselingListsInGoogle->Error trying to remove file {counselor[1]} ALL Grades list csv")
        msgbody += f"Synced {counselor[1]} All list. Gam Status->{stat1}\n" 
        # Sync Lists for Grade 9 for counselor
        gamliststring = counselor[0] + counselor[2] + 'grade9counselinglist'
        filenamestring = counselor[0] + "9" + counselor[1] + ".csv"
        thelogger.info(f"UpdateCounselingListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]}  9th grade list.\n" 
                thelogger.critical(f"UpdateCounselingListsInGoogle->Error trying to remove file {counselor[1]} 9th grade list csv")
        msgbody += f"Synced {counselor[1]} 9th grade list. Gam Status-> {stat1}\n" 
        # Sync Lists for Grade 10 for counselor
        gamliststring = counselor[0] + counselor[2] + "grade10counselinglist"
        filenamestring = counselor[0] + "10" + counselor[1] + ".csv"
        thelogger.info(f"UpdateCounselingListsInGoogle->Running GAM for {gamliststring} using {filenamestring}"
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical(f"UpdateCounselingListsInGoogle->GAM returned an error for the last command")
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]} 10th grade list.\n"
                thelogger.critical(f"UpdateCounselingListsInGoogle->Error trying to remove file {counselor[1]} 10th grade list csv")
        msgbody += f"Synced {counselor[1]} 10th grade list. Gam Status->{stat1}\n"
        # Sync Lists for Grade 11 for counselor
        gamliststring = counselor[0] + counselor[2] + 'grade11counselinglist'
        filenamestring = counselor[0] + "11" + counselor[1] + ".csv"
        thelogger.info(f"UpdateCounselingListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]} 11th grade list.\n" 
                thelogger.critical(f"UpdateCounselingListsInGoogle->Error trying to remove file {counselor[1]} 11th grade list csv")
        msgbody += f"Synced {counselor[1]} 11th grade list. Gam Status->{stat1}\n" 
        # Sync Lists for Grade 12 for counselor
        gamliststring = counselor[0] + counselor[2] + 'grade12counselinglist'
        filenamestring = counselor[0] + "12" + counselor[1] + ".csv"
        thelogger.info(f"UpdateCounselingListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]} 12th grade list.\n" 
                thelogger.critical(f"UpdateCounselingListsInGoogle->Error trying to remove file {counselor[1]} 12th grade list csv")
        msgbody += f"Synced {counselor[1]} 12th grade list. Gam Status->{stat1}\n" 
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