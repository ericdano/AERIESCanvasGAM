import pandas as pd
import os, sys, shlex, subprocess, json, datetime, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
import multiprocessing
import platform
from gam import initializeLogging, CallGAMCommand

"""
Python 3.14

Basically, a Windows version of this crontab job
except it is Python, does some logging, and emails what happens (crontab was doing that though.....)

# /bin/sh
# Shell script remove suspended users from groups
# alias gam="/usr/local/gamadv-xtd3/gam"
# /usr/local/gamadv-xtd3/gam print users query isSuspended=true | /usr/local/gamadv-xtd3/gam csv - gam user ~primaryEmail delete groups

Weekly Script to remove suspended users from google groups

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
  filetempname = '.\\suspendedusers.csv'
  os.chdir(configs['PythonTempDirectory'])
  # GAM Initialization  
  if platform.system() != 'Linux':
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn')
  initializeLogging()
  #
  thelogger.info('RemoveSuspendedUsers->Getting addresses of Suspended Users')
  rc2 = CallGAMCommand(['gam','redirect','csv',filetempname,'print','users','query','isSuspended=True'])

  if rc2 != 0:
    WasThereAnError = True
    thelogger.critical('RemoveSuspendedUsers->GAM Error Getting addresses of Suspended User')
    msgbody += f'RAN gam csv csvfilename.csv gam user ~primaryEmail delete groups. GAM Status->{rc2}\n'  
  thelogger.info('RemoveSuspendedUsers->Running GAM to remove suspended users from groups')
  stat1 = CallGAMCommand(['gam','csv', filetempname, 'gam','user','~primaryEmail', 'delete', 'groups'])

  if stat1 != 0:
    WasThereAnError = True
    thelogger.critical('RemoveSuspendedUsers->GAM returned an error for the last command')
    msgbody += f'ERROR! gam csv csvfilename.csv gam user ~primaryEmail delete groups. GAM Status->{stat1}\n' 
  msgbody += f'RAN gam csv csvfilename.csv gam user ~primaryEmail delete groups. GAM Status->{stat1}\n' 
  thelogger.info('RemoveSuspendedUsers->Success! Ran gam csv csvfilename.csv gam user ~primaryEmail delete groups.')

  """
  This stuff is not needed as Archiving a user will remove licenses
  Kept for Historic reasons

  #Remove Google Licenses from Suspended Users
  # Delete License 1010310008
  thelogger.info('Remove Google License->Removing Student Licenses of Suspended Accounts')
  stat1 = gam.CallGAMCommand(['gam','query','isSuspended=True','del','license','1010310008'])
  if stat1 != 0:
    WasThereAnError = True
    thelogger.critical('Remove Google Licenses 08->GAM returned an error for the last command')
    msgbody += 'ERROR! gam query isSuspended=True del license 1010310008. GAM Status->' + str(stat1) + '\n' 
  msgbody += 'RAN gam query isSuspended=True del license 1010310008. GAM Status->' + str(stat1) + '\n' 
  thelogger.info('Remove Google Licenses->Success! Ran gam query isSuspended=True del license 1010310008.')
  thelogger.info('Remove Google License->Removing Staff Licenses of Suspended Accounts')
  # Delete License 1010310009
  thelogger.info('Remove Google License->Removing Staff Licenses of Suspended Accounts')
  stat1 = gam.CallGAMCommand(['gam','query','isSuspended=True','del','license','1010310009'])
  if stat1 != 0:
    WasThereAnError = True
    thelogger.critical('Remove Google Licenses->GAM returned an error for the last command')
    msgbody += 'ERROR! gam query isSuspended=True del license 1010310009. GAM Status->' + str(stat1) + '\n' 
  msgbody += 'RAN gam query isSuspended=True del license 1010310009. GAM Status->' + str(stat1) + '\n' 
  thelogger.info('Remove Google Licenses->Success! Ran gam query isSuspended=True del license 1010310009.')

"""
  msgbody += 'Done!'
  os.remove(filetempname)
  if WasThereAnError:
    msg['Subject'] = f"🔴 ERROR! {configs['SMTPStatusMessage']} Remove Google License and Groups from Users {datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")}"
  else:
    msg['Subject'] = f"🟢 {configs['SMTPStatusMessage']} Remove Google License and Groups from Users {datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")}"
  end_of_timer = timer()
  msgbody += f'\n\n Elapsed Time= {end_of_timer - start_of_timer}\n'
  msg.set_content(msgbody)
  s = smtplib.SMTP(configs['SMTPServerAddress'])
  s.send_message(msg)
  thelogger.info('RemoveSuspendedUsers->Sent Status message')
  thelogger.info(f'RemoveSuspendedUsers->Done!! - Took {end_of_timer - start_of_timer}')
  print('Done!!!')