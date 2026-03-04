import pandas as pd
import os, sys, shlex, subprocess, json, datetime, gam, multiprocessing, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
"""
Basically, a Windows version of this crontab job
except it is Python, does some logging, and emails what happens (crontab was doing that though.....)

# /bin/sh
# Shell script remove suspended users from groups
# alias gam="/usr/local/gamadv-xtd3/gam"
# /usr/local/gamadv-xtd3/gam print users query isSuspended=true | /usr/local/gamadv-xtd3/gam csv - gam user ~primaryEmail delete groups

Also added GAM stuff to remove Google EDU licenses from Suspended users. 


"""
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
  
  # Go through Google and find accounts suspended but not archived, and then archive them
  # Going to assume that automation using ExpireADAccounts has already removed staff user from any google groups
  # Lists that students are part of get auto regenerated 
  
  thelogger.info('CheckArchivedIfSuspended->Checking if Suspended Accounts are also Archived')
  stat1 = gam.CallGAMCommand(['gam','update','users','query','isSuspended=True isArchived=False','suspended','on','archive','on'])
  if stat1 == 0:
    msgbody += 'RAN gam query isSuspended=True isArchived=False suspended on archive on. GAM Status->' + str(stat1) + '\n' 
  elif stat1 == 2:
    msgbody += 'RAN gam query isSuspended=True isArchived=False suspended on archive on. No users? GAM Status->' + str(stat1) + '\n' 
  else:
    WasThereAnError = True
    thelogger.critical('Archiving Suspended Users returned an error')
    msgbody += 'ERROR! gam query isSuspended=True isArchived=False suspended on archive on. GAM Status->' + str(stat1) + '\n' 
  msgbody += 'Done!'
  if WasThereAnError:
    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " Check if User Archived " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  else:
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " Check if User Archived " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  end_of_timer = timer()
  msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
  msg.set_content(msgbody)
  s = smtplib.SMTP(configs['SMTPServerAddress'])
  s.send_message(msg)
  thelogger.info('CheckArchivedIfSuspended->Sent Status message')
  thelogger.info('CheckArchivedIfSuspended->Done!! - Took ' + str(end_of_timer - start_of_timer))
  print('Done!!!')