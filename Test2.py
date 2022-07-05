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
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE, SUBTREE
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
  with Connection(Server(serverName),
                  user='{0}\\{1}'.format(domainName, userName), 
                  password=password, 
                  auto_bind=True) as conn:

    results = conn.extend.standard.paged_search(search_base= base, 
                                             search_filter = '(objectclass=user)', 
                                             search_scope=SUBTREE,
                                             attributes=['displayName', 'mail', 'userAccountControl','sAMAccountName','accountExpires'],
                                             get_operational_attributes=False, paged_size=15)
  return results

def main():
  configs = getConfigs()
  users = getADSearch('zeus','AUHSD Staff',configs)
  print(users)
  i = 0
  for user in users:
    print('------')
    print(user)
    print(user['attributes'])
#    print(user['attributes']['displayName'])
    i += 1
##  df = pd.json_normalize(users, record_path=['attributes'])
#  print(df)
  print(i)
  exit()
  for user in users:
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