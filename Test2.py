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
  userName = 'edannewitz'
  password = ''
  base = 'OU=' + baseou +',DC=acalanes,DC=k12,DC=ca,DC=us'
  print('Base OU')
  print(domainserver)
  print(baseou)
  print(base)
  server = Server(serverName)
  #conn = Connection(server, read_only=True, user='{0}\\{1}'.format(domainName, userName), password=password, auto_bind=True)
  conn = Connection(server, user='{0}\\{1}'.format(domainName, userName), password=password, auto_bind=True)
  print('Connection Results')
  print(conn.result)
  conn.search(base, '(objectclass=person)', attributes=['displayName', 'mail', 'userAccountControl','sAMAccountName','accountExpires'])
  print(conn)
  return conn

def main():
#  configs = getConfigs()
#  users = getADSearch('zeus','AUHSD Staff',configs)
#  df = pd.DataFrame(columns = ['DN','email','domain'])
#  print(df)
    server = Server('paris')
    conn = Connection(server,user='AUHSD\\tech',password='B@Tmobile',auto_bind=True)
    print(conn)
    conn.search('dc=staff,dc=acalanes,dc=k12,dc=ca,dc=us', '(objectclass=person)')
    print(conn.entries)
if __name__ == '__main__':
    main()