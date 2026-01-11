from ssl import ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE
import pandas as pd
import os, sys, shlex, subprocess, json, logging, gam, smtplib, datetime
from pathlib import Path
from logging.handlers import SysLogHandler
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE, SUBTREE
import arrow

"""

Look for Account Expiration date, and if found, disable AD account, Canvas Account, and Google Account

"""

def getConfigs():
  # Function to get passwords and API keys for Acalanes Canvas and stuff
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  return configs


def DisableCanvasLogins(dataframe,configs):
  global msgbody
  # disable Canvas Logins
  Canvas_API_URL = configs['CanvasAPIURL']
  Canvas_API_KEY = configs['CanvasAPIKey']  
  canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
  for d in dataframe.index:
    if str(dataframe['email'][d]) != '':
      try:
        user = canvas.get_user(str(dataframe['email'][d]),'sis_login_id')
        try:  
          user.edit(user={'event': 'suspend'})
          msgbody += 'Disabled Canvas for ->' + str(dataframe['email'][d]) + '\n'  
          thelogger.info('ExpireADAccounts->Disabled Canvas for ->' + str(dataframe['email'][d]))
        except CanvasException as g:
          msgbody += 'Error Disabling with Canvas ->' + str(dataframe['email'][d]) + ' ' + str(g) + '\n'  
          thelogger.info('ExpireADAccounts->Error Disabling with Canvas ->' + str(dataframe['email'][d]) + ' ' + str(g))
      except CanvasException as e:
        msgbody += 'Error Disabling with Canvas ->' + str(dataframe['email'][d]) + ' ' + str(e) + '\n'  
        thelogger.info('ExpireADAccounts->Error Disabling with Canvas ->' + str(dataframe['email'][d]) + ' ' + str(e))

def modifyADUsers(dataframe,configs):
  for d in dataframe.index:
    serverName = 'LDAP://' + dataframe['domain'][d]
    domainName = 'AUHSD'
    userName = 'tech'
    password = configs['ADPassword']
    base = 'DC=acalanes,DC=k12,DC=ca,DC=us'
    server = Server(serverName)
    ClearPhone =''
    
    conn = Connection(server, user='{0}\\{1}'.format(domainName, userName), password=password, auto_bind=True)
    conn.modify(dataframe['DN'][d], {'userAccountControl': [('MODIFY_REPLACE', 2)]})
    conn.modify(dataframe['DN'][d], {'telephoneNumber': [('MODIFY_DELETE',[])],
                                     'Pager':  [('MODIFY_DELETE',[])],
                                     'ipPhone':  [('MODIFY_DELETE',[])]})

    # This is how you disable an account, you modify it to be 2 rather than 512
    thelogger.info('ExpireADAccounts->Disabled AD for user')

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

def DisableGoogle(dataframe):
  global msgbody
  for d in dataframe.index:
    if 'auhsdschools.org' in str(dataframe['email'][d]):
      gam.initializeLogging()
      stat = gam.CallGAMCommand(['gam','update', 'user', str(dataframe['email'][d]), 'suspended', 'on', 'ou', '/Former Staff'])
      if stat != 0:
        msgbody += 'Error with Google suspending ' + str(dataframe['email'][d]) + '\n'
        thelogger.info('ExpireADAccounts->Error with Google suspending ' + str(dataframe['email'][d]))
      else:
        msgbody += 'Suspended Google Account->' + str(dataframe['email'][d]) + '\n'
        thelogger.info('ExpireADAccounts->Suspended Google Account->' + str(dataframe['email'][d]))
        
def main():
  global msgbody,thelogger
  configs = getConfigs()
#  configsAE = getConfigsAE()
  thelogger = logging.getLogger('MyLogger')
  thelogger.setLevel(logging.DEBUG)
  handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
  thelogger.addHandler(handler)
  thelogger.info('ExpireADAccounts->Connecting to Zeus...')
  msgbody += 'Checking domain server Zeus....\n'
  users = getADSearch('zeus','AUHSD Staff',configs)
 # print(users.entries)
  df = pd.DataFrame(columns = ['DN','email','domain'])
  """
  I love Pandas.....Express and the Dataframe. 
  create a dataframe to put all the LDAP search results in so we can process them
  """
  for user in users:  
    if (user['attributes']['userAccountControl'] == 512):
      # Expired accounts show as normal accounts, but you have to find the date
      # and a normal account has the accountExpires date set to 1601-01-01
      # so anything bigger than that is an account that should be properly disabled
      accountExpiresDate = arrow.get(str(user['attributes']['accountExpires']))
      if (accountExpiresDate < arrow.utcnow()) and (accountExpiresDate > arrow.get('1601-01-01T00:00:00+00:00')):
        """
        df = df.append({'DN': str(user['dn']),
                          'email': str(user['attributes']['mail']),
                          'domain': 'zeus'},ignore_index=True)
        """
        tempDF = pd.DataFrame([{'DN': str(user['dn']),
                          'email': str(user['attributes']['mail']),
                          'domain': 'zeus'}])
        df = pd.concat([df,tempDF], axis=0, ignore_index=True)
        msgbody += f"Found user->{user['attributes']['sAMAccountName']} {user['attributes']['mail']} on Zeus whos account is expired but not disabled ({user['dn']})\n"
        thelogger.info('ExpireADAccounts->' + f"Found user->{user['attributes']['sAMAccountName']} {user['attributes']['mail']} on Zeus whos account is expired but not disabled ({user['dn']})")
  msgbody += 'Checking domain server Paris....\n'
  thelogger.info('ExpireADAccounts->Connecting to Paris...')
  users2 = getADSearch('paris','Acad Staff,DC=staff',configs)
# Now check the staff domain
  for user in users2:
    if (user['attributes']['userAccountControl'] == 512):
      # Expired accounts show as normal accounts, but you have to find the date
      # and a normal account has the accountExpires date set to 1601-01-01
      # so anything bigger than that is an account that should be properly disabled
      accountExpiresDate = arrow.get(str(user['attributes']['accountExpires']))
      if (accountExpiresDate < arrow.utcnow()) and (accountExpiresDate > arrow.get('1601-01-01T00:00:00+00:00')):
        tempDF2 = pd.DataFrame([{'DN': str(user['dn']),
                          'email': str(user['attributes']['mail']),
                          'domain': 'paris'}])
        df = pd.concat([df,tempDF2], axis=0, ignore_index=True)
        msgbody += f"Found user->{user['attributes']['sAMAccountName']} {user['attributes']['mail']} on Paris whos account is expired but not disabled ({user['dn']})\n"
        thelogger.info('ExpireADAccounts->' + f"Found user->{user['attributes']['sAMAccountName']} {user['attributes']['mail']} on Paris whos account is expired but not disabled ({user['dn']})")
  if df.empty:
    msgbody += 'No Accounts are expired. Nothing to do. We will try again later....\n'
    thelogger.info('ExpireADAccounts->No Accounts found that are expiring')
  else:
    modifyADUsers(df,configs)
    DisableGoogle(df)
    #DisableCanvasLogins(df,configs)
  msg = EmailMessage()
  msg['Subject'] = str(configs['SMTPStatusMessage'] + " Look for expired accounts script " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  msg['From'] = configs['SMTPAddressFrom']
  msg['To'] = configs['SendInfoEmailAddr']
  msg.set_content(msgbody)
  s = smtplib.SMTP(configs['SMTPServerAddress'])
  s.send_message(msg)
  print('Done')

if __name__ == '__main__':
  msgbody = ''
  main()

