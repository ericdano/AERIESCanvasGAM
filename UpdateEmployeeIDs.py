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


def getConfigs():
  # Function to get passwords and API keys for Acalanes Canvas and stuff
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  return configs

def getADSearch(domainserver,baseou,configs):
  serverName = 'LDAP://' + domainserver
  domainName = 'AUHSD'
  userName = 'tech'
  password = configs['ADPassword']
  base = 'OU=' + baseou +',DC=acalanes,DC=k12,DC=ca,DC=us'
  with Connection(Server(serverName),
                  user='{0}\\{1}'.format(domainName, userName), 
                  password=password, 
                  auto_bind=True,
                  return_empty_attributes=False) as conn:

    results = conn.extend.standard.paged_search(search_base= base, 
                                             search_filter = '(objectclass=user)', 
                                             search_scope=SUBTREE,
                                             attributes=['displayName', 'mail', 'userAccountControl','sAMAccountName','employeeID'],
                                             get_operational_attributes=False,paged_size=15)
  return results

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
  dataframe1 = pd.read_sql_query('SELECT ID, HRID, FN, LN, EM FROM STF WHERE EM =  \'nsoja@auhsdschools.org\' ORDER BY LN',engine)
#  dataframe1 = pd.read_sql_query('SELECT ID, HRID, FN, LN, EM FROM STF ORDER BY LN',engine)

  print(dataframe1)
  #dataframe1.to_csv('e:\PythonTemp\AllEmp.csv')
  msgbody += 'Checking domain server Zeus....\n'
  users = getADSearch('zeus','AUHSD Staff',configs)
  users2 = getADSearch('paris','Acad Staff,DC=staff',configs)
  for user in users:
    if "auhsdschools.org" in str(user['attributes']['mail']):
      print(str(user['attributes']['displayName']) + ' ' + str(user['attributes']['mail']) + ' ' + str(user['attributes']['employeeID']))
      if user['attributes']['employeeID'] is None:
        print('Found one') 
      print(type(user['attributes']['employeeID']))
  for user in users2:
    if "auhsdschools.org" in str(user['attributes']['mail']):
      print(str(user['attributes']['displayName']) + ' ' + str(user['attributes']['mail']) + ' ' + str(user['attributes']['employeeID']))
      if len(str(user['attributes']['employeeID'])) == 0:
        print('Found another')
      print(type(user['attributes']['employeeID']))

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
