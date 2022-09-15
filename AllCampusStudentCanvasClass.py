import pandas as pd
import os, sys, pyodbc, shlex, subprocess, gam, datetime, json, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

# This scrip pull ALL students from AERIES from a site, and puts them into a Canvas Group
#

def GetAERIESData(thelogger):
    conn = pyodbc.connect('Driver={SQL Server};'
                        'Server=SATURN;'
                        'Database=DST22000AUHSD;'
                        'Trusted_Connection=yes;')
    thelogger.info('All Campus Student Canvas Groups->Connecting To AERIES to get ALL students for Campus')
    cursor = conn.cursor()
    sql_query = pd.read_sql_query('SELECT ID, SEM, SC FROM STU WHERE DEL=0 AND STU.TG = \'\' AND (SC < 8 OR SC = 30) AND SP <> \'2\'',conn)
    conn.close()
    thelogger.info('All Campus Student Canvas Groups->Closed AERIES connection')
    sql_query.sort_values(by=['SC'])
    return sql_query


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
    #populate a table
    sites = [ ('LLHS','1',''),
                ('AHS','2',''),
                ('MHS','3',''),
                ('CHS','4',''),
                ('ACIS','6',''),
                ('CENR','7',''),
                ('TRANS','30'.'') ]

    AERIESData = GetAERIESData(thelogger)

    for site in sites:
        print(AERIESData.loc[AERIESData['SC']==site[0][1]])
        #thelogger.info('UpdateCounselingListsInGoogle->Running GAM for ' + tempstr1 + 'using ' + tempstr2)
 
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