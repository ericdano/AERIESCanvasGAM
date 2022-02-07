import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json, logging, smtplib, datetime
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging
ImportCSV = Path.home() / ".Acalanes" / "CanvasCounselingGroups.csv"
logfilename = Path.home() / ".Acalanes" / configs['logfilename']
logging.basicConfig(filename=str(logfilename), level=logging.INFO)
logging.info('Loaded config file and logfile started for AUHSD Suspend Users')
logging.info('Loading To Suspend CSV file')
#prep status (msg) email
msg = EmailMessage()
msg['Subject'] = str(configs['SMTPStatusMessage'] + " Suspend Users " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
#ToSuspend = pd.read_csv(ImportCSV)
conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
#
cursor = conn.cursor()
#-----Canvas Info
Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
logging.info('Connecting to Canvas')
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
# Go through the counseling list, then add or remove students from groups
msgbody += 'Starting Suspend for AUHSD Script\n'
try:
    user = canvas.get_user()
