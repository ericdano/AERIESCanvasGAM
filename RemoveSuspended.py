import pandas as pd
import os, sys, shlex, subprocess, json, datetime, gam, multiprocessing, smtplib, logging
from pathlib import Path
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
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  thelogger = logging.getLogger('MyLogger')
  thelogger.setLevel(logging.DEBUG)
  handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
  thelogger.addHandler(handler)
  thelogger.info('Remove Sus')
  msg = EmailMessage()
  msg['Subject'] = str(configs['SMTPStatusMessage'] + " Remove Suspended Users From Groups - " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  msg['From'] = configs['SMTPAddressFrom']
  msg['To'] = configs['SendInfoEmailAddr']
  msgbody = ''
  if sys.platform == 'darwin':
    multiprocessing.set_start_method('fork')
  gam.initializeLogging()
  thelogger.info('RemoveSuspendedUsers->Getting addresses of Suspended Users')
  rc2 = gam.CallGAMCommand(['gam','print','users','query','isSuspended=true'])
#  if rc2 != 0:
#    thelogger.critical('LapSwimEmailSync->GAM Error getting Google sheet')