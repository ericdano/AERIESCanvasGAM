import pandas as pd
import os, sys, shlex, subprocess, json, logging, smtplib, datetime
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from timeit import default_timer as timer
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

WasThereAnErr = False
start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging
if configs['logserveraddress'] is None:
    logfilename = Path.home() / ".Acalanes" / configs['logfilename']
    thelogger = logging.getLogger('MyLogger')
    thelogger.basicConfig(filename=str(logfilename), level=thelogger.info)
else:
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)

Canvas_API_URL = configs['CanvasAPIURL']
#----------------------------------------

Canvas_API_KEY = configs['CanvasAPIKey']
thelogger.info('Canvas ACIS Groups for Counselors->Connecting to Canvas')
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
gradingperiod=account.get_grading_periods()
for i in gradingperiod:
   print(str(i.id) + " "+ str(i.title) + " is it closed? " + str(i.is_closed) + " start date:" + str(i.start_date) + " end date:" + str(i.end_date))
# Go through the counseling list, then add or remove students from groups
