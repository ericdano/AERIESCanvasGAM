import pandas as pd
import os, sys, shlex, subprocess, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

"""
This script pulls ALL students from AERIES. Sorts them by site and grade, and puts them into a Canvas Course for the site,
and section in that course by Grade

"""
def main():
    start_of_timer = timer()
    WasThereAnError = False  
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    if configs['logserveraddress'] is None:
        logfilename = Path.home() / ".Acalanes" / configs['logfilename']
        thelogger = logging.getLogger('MyLogger')
        thelogger.basicConfig(filename=str(logfilename), level=thelogger.info)
    else:
        thelogger = logging.getLogger('MyLogger')
        thelogger.setLevel(logging.DEBUG)
        handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
        thelogger.addHandler(handler)

    #prep status (msg) email
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['SendInfoEmailAddr']
    msgbody = ''
    Canvas_API_URL = configs['CanvasAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    account = canvas.get_account(1)
    course = canvas.get_course(11069)   
    assignments = course.get_assignments(workflow_state='deleted')
    for assignment in assignments:
        print(assignment)
        print(assignment.workflow_state)
    '''
    end_of_timer = timer()
    if WasThereAnError == True:
        msg['Subject'] = "ERROR!! -> Canvas Catch-all Informational Course Update"
    else:
        msg['Subject'] = "Canvas Catch-all Informational Course Update"
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    thelogger.info('AUHSD Catchall Course Update->->Sent status message')
    thelogger.info('AUHSD Catchall Course Update->->DONE! - took ' + str(end_of_timer - start_of_timer))
    '''
    print('Done!!!')

if __name__ == '__main__':
    main()