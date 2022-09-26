import pandas as pd
import os, sys, shlex, gam, subprocess, json, logging, smtplib, datetime
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

"""
Python Script to suspend all users in a certain OU
In this case, it suspends all the users in OU Z-Former Students
and any users in any sub OUs
"""

def main():
  start_of_timer = timer()
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
      configs = json.load(f)
  thelogger = logging.getLogger('MyLogger')
  thelogger.setLevel(logging.DEBUG)
  handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
  thelogger.addHandler(handler)
  #prep status (msg) email
  msg = EmailMessage()
  msg['From'] = configs['SMTPAddressFrom']
  msg['To'] = configs['SendInfoEmailAddr']
  msgbody = ''
  thelogger.info('WeeklyStudentSuspend->Starting GAM Suspension')
  stat = gam.CallGAMCommand(['gam','ou_and_children','/Z-Former Students','update','user','suspended','true'])
  if stat != 0:
    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " Weekly Student Suspension Script " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  else:
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " Weekly Student Suspension Script " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
  end_of_timer = timer()
  msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
  msg.set_content(msgbody)
  s = smtplib.SMTP(configs['SMTPServerAddress'])
  s.send_message(msg)
  thelogger.info('WeeklyStudentSuspend->Sent status message')
  thelogger.info('WeeklyStudentSuspend->DONE! - took ' + str(end_of_timer - start_of_timer))
  print('Done!!!')
  
if __name__ == '__main__':
  main()