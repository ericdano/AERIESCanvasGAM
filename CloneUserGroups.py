import pandas as pd
import os, sys, shlex, subprocess, gam, datetime, json, smtplib, logging
from pathlib import Path
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
import glob
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
#Logging
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
thelogger.info('Cloning User Group')
stat1 = gam.CallGAMCommand(['gam','redirect', 'stdout', 'clonegroups.csv', 'redirect', 'stderr','stdout','user', 'ncarpenter','print','groups']) 
if stat1 != 0:
    WasThereAnError = True
end_of_timer = timer()
msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
msg.set_content(msgbody)
s = smtplib.SMTP(configs['SMTPServerAddress'])
s.send_message(msg)
thelogger.info('UpdateACISStuParentListsInGoogle->Sent status message')
thelogger.info('UpdateACISStuParentListsInGoogle->Done - Took ' + str(end_of_timer - start_of_timer))
print('Done!!!')
