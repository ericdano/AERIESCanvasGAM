from ssl import ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE
import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json, logging, gam, smtplib, datetime
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE
import arrow

def getConfigs():
  # Function to get passwords and API keys for Acalanes Canvas and stuff
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  return configs

def getConfigsAE():
  # Function to get passwords and API keys for Adult Ed Canvas and stuff
  confighome = Path.home() / ".ASAPCanvas" / "ASAPCanvas.json"
  with open(confighome) as f:
    configs = json.load(f)
  return configs

def connectCanvas(configs):
  # Generic connect to Canvas function
  Canvas_API_URL = configs['CanvasAPIURL']
  Canvas_API_KEY = configs['CanvasAPIKey']  
  canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
  return canvas

def DisableCanvasLogins(dataframe,configs,configsae):
  # disable Canvas Logins
  for d in dataframe.index:
    if str(dataframe['email'][d]) != '':
      if ('OU=AE' in str(dataframe['DN'][d])):
        # Adult Ed teachers are in the OU=AE from LDAP. 
        # So we just need to see if the string has OU=AE in it, then we need to use the AE Canvas
        canvas = connectCanvas(configsae)
      else:
        canvas = connectCanvas(configs)
      try:
        user = canvas.get_user(str(dataframe['email'][d]),'sis_login_id')
        try:  
          user.edit(user={'event': 'suspend'})
        except CanvasException as g:
          print(g)  
      except CanvasException as e:
        print(e)

def modifyADUsers(dataframe,configs):
  for d in dataframe.index:
    serverName = 'LDAP://' + dataframe['domain'][d]
    domainName = 'AUHSD'
    userName = 'tech'
    password = configs['ADPassword']
    base = 'DC=acalanes,DC=k12,DC=ca,DC=us'
    server = Server(serverName)
    conn = Connection(server, user='{0}\\{1}'.format(domainName, userName), password=password, auto_bind=True)
    conn.modify(dataframe['DN'][d], {'userAccountControl': [('MODIFY_REPLACE', 2)]})
    # This is how you disable an account, you modify it to be 2 rather than 512

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

def DisableGoogle(dataframe):
  for d in dataframe.index:
    if 'auhsdschools.org' in str(dataframe['email'][d]):
      gam.initializeLogging()
      stat1 = gam.CallGAMCommand(['gam','update', 'user', str(dataframe['email'][d]), 'suspended', 'on', 'ou', '/Former Staff'])
  return stat1

def main():
  msgbody = ''
  configs = getConfigs()
  configsAE = getConfigsAE()
  users = getADSearch('zeus','AUHSD Staff',configs)
 # print(users.entries)
  df = pd.DataFrame(columns = ['DN','email','domain'])
  # we love Pandas.....Express and the Dataframe. 
  # create a dataframe to put all the LDAP search results in so we can process them
  for user in users.entries:
    if (user.userAccountControl == 512):
      # Expired accounts show as normal accounts, but you have to find the date
      # and a normal account has the accountExpires date set to 1601-01-01
      # so anything bigger than that is an account that should be properly disabled
      accountExpiresDate = arrow.get(str(user.accountExpires))
      if (accountExpiresDate < arrow.utcnow()) and (accountExpiresDate > arrow.get('1601-01-01T00:00:00+00:00')):
        df = df.append({'DN': user.entry_dn,
                          'email': user.mail,
                          'domain': 'zeus'},ignore_index=True)
        msgbody += f'Found user->{user.entry_dn} {user.mail} on Zeus whos account is to expire\n'

  users.unbind()
  users2 = getADSearch('paris','Acad Staff,DC=staff',configs)
#  print(users2.entries)
  for user in users2.entries:
    if (user.userAccountControl == 512):
      # Expired accounts show as normal accounts, but you have to find the date
      # and a normal account has the accountExpires date set to 1601-01-01
      # so anything bigger than that is an account that should be properly disabled
      accountExpiresDate = arrow.get(str(user.accountExpires))
      if (accountExpiresDate < arrow.utcnow()) and (accountExpiresDate > arrow.get('1601-01-01T00:00:00+00:00')):
        df = df.append({'DN': user.entry_dn,
                          'email': user.mail,
                          'domain': 'paris'},ignore_index=True)
        msgbody += f'Found user->{user.entry_dn} {user.mail} on Paris whos account is to expire\n'
  users2.unbind()
  modifyADUsers(df,configs)
  DisableGoogle(df)
  DisableCanvasLogins(df,configs,configsAE)
  msg = EmailMessage()
  msg['Subject'] = str(configs['SMTPStatusMessage'] + " Look for expired accounts script " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  msg['From'] = configs['SMTPAddressFrom']
  msg['To'] = configs['SendInfoEmailAddr']
  msg.set_content(msgbody)
  s = smtplib.SMTP(configs['SMTPServerAddress'])
  s.send_message(msg)
if __name__ == '__main__':
    main()
