from ssl import ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE
import pandas as pd
import os, sys, shlex, subprocess, json, logging, smtplib, datetime
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE, SUBTREE
from logging.handlers import SysLogHandler
import arrow
from ms_active_directory import ADDomain

def getConfigs():
  # Function to get passwords and API keys for Acalanes Canvas and stuff
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  return configs

def getADSearch(domain,useremail,configs):
#  serverName = 'LDAP://' + domainserver
  if domain == 'staff':
    domainname = 'staff.acalanes.k12.ca.us'
  else:
    domainname = 'acalanes.k12.ca.us'
  userName = 'tech'
  password = configs['ADPassword']
  domain = ADDomain(domainname)
  session = domain.create_session_as_user('tech@acalanes.k12.ca.us',password)
  user = session.find_user_by_sam_name(useremail,['employeeID'])
  return(user)


def main():
  global msgbody,thelogger
  configs = getConfigs()
  thelogger = logging.getLogger('MyLogger')
  thelogger.setLevel(logging.DEBUG)
  handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
  thelogger.addHandler(handler)
  #connection_string = "DRIVER={SQL Server};SERVER=SATURN;DATABASE=DST22000AUHSD;Trusted_Connection=yes"
  msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
  connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
  connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
  engine = create_engine(connection_url)    
  with engine.begin() as connection:
    dataframe1 = pd.read_sql_query('SELECT ID, HRID, FN, LN, EM FROM STF ORDER BY LN',connection)
    dataframe1["EM"] = dataframe1["EM"].str.replace("@auhsdschools.org","")
  print(dataframe1)
  #dataframe1.to_csv('e:\PythonTemp\AllEmp.csv')
  msgbody += 'Checking domain server Zeus....\n'
  user = getADSearch('auhsd','mroberts',configs)
  if user is None:
    user = getADSearch('staff','mroberts',configs)
  print(user)
  print(user.get('employeeID'))
  employeeID = user.get('employeeID')
  msg = EmailMessage()
  msg['Subject'] = str(configs['SMTPStatusMessage'] + " Look Employee ID Updates script " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  msg['From'] = configs['SMTPAddressFrom']
  msg['To'] = configs['SendInfoEmailAddr']
  msg.set_content(msgbody)
  s = smtplib.SMTP(configs['SMTPServerAddress'])
  s.send_message(msg)
if __name__ == '__main__':
  msgbody = ''
  main()
