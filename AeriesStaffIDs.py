import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json, logging
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor = conn.cursor()                 
dataframe1 = pd.read_sql_query('SELECT ID, HRID, FN, LN, EM FROM STF WHERE EM =  \'adhaliwal@auhsdschools.org\' ORDER BY LN',conn)
print(dataframe1)

Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
user = account.get_users(search_term=str('adhaliwal@auhsdschools.org'))
print(user[0].sis_user_id)

