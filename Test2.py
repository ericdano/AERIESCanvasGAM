from ssl import ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE
import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json, logging, gam
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE
from datetime import datetime
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
  server = Server(serverName)
  #conn = Connection(server, read_only=True, user='{0}\\{1}'.format(domainName, userName), password=password, auto_bind=True)
  conn = Connection(server, user='{0}\\{1}'.format(domainName, userName), password=password, auto_bind=True)
  conn.search(base, '(objectclass=person)', attributes=['displayName', 'mail', 'userAccountControl','sAMAccountName','accountExpires'])
  return conn

def main():
  configs = getConfigs()
  users = getADSearch('zeus','AUHSD Staff',configs)
  df = pd.DataFrame(columns = ['DN','email','domain','userAccountControl','sAMAccountName','accountExpires'])
  for user in users.entries:
    df = df.append({'DN': user.entry_dn,
                        'email': user.mail,
                        'domain': 'paris',
                        'userAccountControl' : user.userAccountControl,
                        'sAMAccountName': user.sAMAccountName,
                        'accountExpires' : user.accountExpires},ignore_index=True)
    if str(user.mail) == 'sgoswami@auhsdschools.org':
      print('Found!')
      print(user)
    if str(user.displayName) == 'Sukanya Goswami':
      print('Found!')
      print(user)
  print(df)
  df.to_csv('DumpofAUHSD.csv')
if __name__ == '__main__':
    main()