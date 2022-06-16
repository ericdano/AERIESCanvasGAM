from ssl import ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE
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
from ldap3 import Server, Connection
from datetime import datetime
import arrow

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST22000AUHSD;'
                      'Trusted_Connection=yes;')
cursor = conn.cursor()                 
dataframe1 = pd.read_sql_query('SELECT ID, HRID, FN, LN, EM FROM STF WHERE EM =  \'kdenton@auhsdschools.org\' ORDER BY LN',conn)
#print(dataframe1)

serverName = 'LDAP://zeus'
domainName = 'AUHSD'
userName = 'tech'
password = configs['ADPassword']
base = 'OU=AUHSD Staff,DC=acalanes,DC=k12,DC=ca,DC=us'

server = Server(serverName)
conn = Connection(server, read_only=True, user='{0}\\{1}'.format(domainName, userName), password=password, auto_bind=True)

conn.search(base, '(objectclass=person)', attributes=['displayName', 'mail', 'userAccountControl','sAMAccountName','accountExpires'])
smaller = 0
bigger = 0
for i in conn.entries:
  if (i.userAccountControl == 512):
    # Expired accounts show as normal accounts, but you have to find the date
    # and a normal account has the accountExpires date set to 1601-01-01
    # so anything bigger than that is an account that should be properly disabled
    d = arrow.get(str(i.accountExpires))
    if (d<arrow.utcnow()) and (d>arrow.get('1601-01-01T00:00:00+00:00')):
      print(i.sAMAccountName)
      print(i.displayName)
      print(i.mail)
      #print(i.userAccountControl)
      print(d)
      print('-----')

  #if (i.userAccountControl == 512) and (d < arrow.utcnow()):
  #  print(str(i.sAMAccountName) + ' ' + str(i.displayName) + ' ' + str(i.mail) + ' ' + str(i.userAccountControl) + ' ' + str(i.accountExpires))
  #  print('------') 
    #print('USER = {0} : {1} : {2}'.format(i.sAMAccountName.values[0], i.displayName.values[0], i.userAccountControl.values[0]))
  #if i.userAccountControl == 514:
  #  print(i.sAMAccountName)
  #  print(i.displayName)
  #  print(i.mail)
  #  print(i.userAccountControl)
  #  print('------')
  #if i.displayName == 'Karen Findlay':
  #  print(i.sAMAccountName)
  #  print(i.displayName)
  #  print(i.mail)
  #  print(i.userAccountControl)
   # print(i.accountExpires)
  #  print('------') 
    #print(i['mail'])
  #print(i['enabled'])
#q = adquery.ADQuery()

#q.execute_query(
#    attributes = ["distinguishedName", "description"],
#    where_clause = "objectClass = '*'",
#    base_dn = "OU=AUHSD Staff, DC=acalanes, DC=k12, DC=ca, DC=us"
#)
#for row in q.get_results():
#    print(row)

#Canvas_API_URL = configs['CanvasAPIURL']
#Canvas_API_KEY = configs['CanvasAPIKey']
#canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
#account = canvas.get_account(1)
#user = account.get_users(search_term=str('kdenton@auhsdschools.org'))
#print(user[0].sis_user_id)
#print(user[0].sortable_name)
#user = account.get_users(search_term='Greg costa')
#print(user[0].sis_user_id)
#print(user[0].sortable_name)
#myuser = aduser.ADUser.from_cn("edannewitz")
#print(myuser)
if __name__ == '__main__':
    main()