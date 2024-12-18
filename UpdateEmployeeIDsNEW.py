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
import ldap3
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE, SUBTREE, ALL_ATTRIBUTES
from logging.handlers import SysLogHandler
import arrow
from ms_active_directory import ADDomain

def getConfigs():
  # Function to get passwords and API keys for Acalanes Canvas and stuff
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  return configs


'''
def getADSearch(domainserver,baseou,configs):
  serverName = 'LDAP://' + domainserver
  domainName = 'AUHSD'
  userName = 'tech'
  password = configs['ADPassword']
  base = 'OU=' + baseou +',DC=acalanes,DC=k12,DC=ca,DC=us'
  with Connection(Server(serverName, get_info=ldap3.ALL_ATTRIBUTES),
                  user='{0}\\{1}'.format(domainName, userName), 
                  password=password, 
                  auto_bind=True) as conn:

    results = conn.extend.standard.paged_search(search_base= base, 
                                             search_filter = '(objectclass=user)', 
                                             search_scope=SUBTREE,
                                             attributes=['displayName','mail','userAccountControl','sAMAccountName','employeeID'],
                                             get_operational_attributes=False, paged_size=15)
  return results
'''

def getADSearch(domainserver,baseou,configs,datafr):
  serverName = domainserver + '.acalanes.k12.ca.us'
  domainName = 'AUHSD'
  userName = 'tech'
  password = configs['ADPassword']
  base = 'OU=' + baseou +',DC=acalanes,DC=k12,DC=ca,DC=us'
  server = ldap3.Server(serverName,get_info=ldap3.ALL)
  conn = ldap3.Connection(server, user='{0}\\{1}'.format(domainName,userName), password=password, auto_bind=True)
  search_base = 'OU=AUHSD Staff'
  search_filter = '(objectClass=user)'  # Adjust if needed to target specific users
  attributes = ['employeeID','mail','sAMAccountName','displayName','userAccountControl']
  # Perform the search
  conn.search(search_base, search_filter, attributes=attributes)
  # Iterate over the results and extract the employeeID

  for entry in conn.entries:
    try:
        employee_id = entry['employeeID'].value
        mail = str(entry['mail'])
        sAMAccountName = str(entry['sAMAccountName'])
        displayname = str(entry['displayName'])
        useraccountcontrol = str(entry['userAccountControl'])
        print(f"Employee ID: {employee_id} email: {mail} SAMAccount: {sAMAccountName} DisplayName: {displayname} userACC: {useraccountcontrol}")
        datafr = pd.DataFrame([{'DN': displayname,
                          'email': mail,
                          'employeeID': employee_id,
                          'domain': domainserver}])
    except ldap3.core.exceptions.LDAPKeyError:
        print("employeeID attribute not found for this user")


    df = pd.concat([df,datafr], axis=0, ignore_index=True)
# Unbind (disconnect) from the server 
  conn.unbind()
  return df


def main():
  global msgbody,thelogger
  configs = getConfigs()
  thelogger = logging.getLogger('MyLogger')
  thelogger.setLevel(logging.DEBUG)
  handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
  thelogger.addHandler(handler)
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
  df = pd.DataFrame(columns = ['DN','email','employeeID','domain'])

  users = getADSearch('zeus','AUHSD Staff',configs,df) 

  thelogger.info('ExpireADAccounts->Connecting to Paris...')
  users2 = getADSearch('paris','Acad Staff,DC=staff',configs,df)

  '''
  for user in users:  
    tempDF = pd.DataFrame([{'DN': str(user['dn']),
                          'email': str(user['attributes']['mail']),
                          'employeeID': str(user['employeeID']),
                          'domain': 'zeus'}])
    df = pd.concat([df,tempDF], axis=0, ignore_index=True)
  for user in users2:  
    tempDF2 = pd.DataFrame([{'DN': str(user['dn']),
                          'email': str(user['attributes']['mail']),
                          'employeeID': str(user['attributes']['employeeID']),
                          'domain': 'zeus'}])
    df = pd.concat([df,tempDF], axis=0, ignore_index=True)
  '''
  print(df)

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
