import pandas as pd
import os, sys, shlex, subprocess, json, datetime, gam, multiprocessing, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

# /bin/sh
# Shell script remove suspended users from groups
# alias gam="/usr/local/gamadv-xtd3/gam"
# /usr/local/gamadv-xtd3/gam print users query isSuspended=true | /usr/local/gamadv-xtd3/gam csv - gam user ~primaryEmail delete groups

if __name__ == '__main__':
# One time initialization
  start_of_timer = timer()
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  thelogger = logging.getLogger('MyLogger')
  thelogger.setLevel(logging.DEBUG)
  handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
  thelogger.addHandler(handler)
  thelogger.info('RemoveSuspendedUsers->Starting Remove Suspended Users From Groups')
  msg = EmailMessage()
  msg['From'] = configs['SMTPAddressFrom']
  msg['To'] = configs['SendInfoEmailAddr']
  msgbody = ''
  WasThereAnError = False
  filetempname = '.\suspendedusers.csv'
  os.chdir('E:\\PythonTemp')
  if sys.platform == 'darwin':
    multiprocessing.set_start_method('fork')
  gam.initializeLogging()
  thelogger.info('RemoveSuspendedUsers->Getting addresses of Suspended Users')
  rc2 = gam.CallGAMCommand(['gam','redirect','csv',filetempname,'print','users','query','isSuspended=true'])
  if rc2 != 0:
    WasThereAnError = True
    thelogger.critical('RemoveSuspendedUsers->GAM Error Getting addresses of Suspended User')
    msgbody += 'Ran gam csv csvfilename.csv gam user ~primaryEmail delete groups. GAM Status->' + str(stat1) + '\n'  
  thelogger.info('RemoveSuspendedUsers->Running GAM to remove suspended users from groups')
  stat1 = gam.CallGAMCommand(['gam','csv', filetempname, 'gam','user','~primaryEmail', 'delete', 'groups'])
  if stat1 != 0:
    WasThereAnError = True
    thelogger.critical('UpdateCounselingListsInGoogle->GAM returned an error for the last command')
    msgbody += 'ERROR! gam csv csvfilename.csv gam user ~primaryEmail delete groups. GAM Status->' + str(stat1) + '\n' 
  msgbody += 'Ran gam csv csvfilename.csv gam user ~primaryEmail delete groups. GAM Status->' + str(stat1) + '\n' 
  thelogger.info('RemoveSuspendedUsers->Success! Ran gam csv csvfilename.csv gam user ~primaryEmail delete groups.')
  os.remove(filetempname)
  msgbody += 'Done!'
  if WasThereAnError:
    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " Remove Suspended Users From Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  else:
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " Remove Suspended Users From Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  end_of_timer = timer()
  msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
  msg.set_content(msgbody)
  s = smtplib.SMTP(configs['SMTPServerAddress'])
  s.send_message(msg)
  thelogger.info('RemoveSuspendedUsers->Sent Status message')
  thelogger.info('RemoveSuspendedUsers->Done!! - Took ' + str(end_of_timer - start_of_timer))
  print('Done!!!')