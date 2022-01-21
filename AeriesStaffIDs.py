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

conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor = conn.cursor()                 
dataframe1 = pd.read_sql_query('SELECT HRID, FN, LN, EM FROM STF ORDER BY LN',conn)
print(dataframe1)