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

#This script finds counselors and their assigned students in AERIES, then updates Google Group Annouce only lists with any student changes

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
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
    WasThereAnError = False
    # Change directory to a TEMP Directory where GAM and Python can process CSV files 
    os.chdir('E:\\PythonTemp')
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
    GetAERIESData(thelogger,configs)

    print('Done!!!')

if __name__ == '__main__':
    main()