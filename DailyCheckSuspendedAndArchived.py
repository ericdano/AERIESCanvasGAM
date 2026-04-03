import pandas as pd
import os, sys, shlex, subprocess, json, datetime, gam, multiprocessing, smtplib, logging, socket
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
    msgbody += f'RAN gam query isSuspended=True isArchived=False suspended on archive on. GAM Status->{stat1}\n'
  elif stat1 == 2:
    msgbody += f'RAN gam query isSuspended=True isArchived=False suspended on archive on. No users? GAM Status->{stat1}\n'
  else:
    WasThereAnError = True
    thelogger.critical('Archiving Suspended Users returned an error')
    msgbody += f'ERROR! gam query isSuspended=True isArchived=False suspended on archive on. GAM Status->' + str(stat1) + '\n' 
  msgbody += 'Done!'
  if WasThereAnError:
    msg['Subject'] = f"🔴 ERROR! {configs['SMTPStatusMessage']} Check if User Archived {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"
  else:
    msg['Subject'] = f"🟢 {configs['SMTPStatusMessage']} Check if User Archived {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"
  end_of_timer = timer()
  msgbody += f'\n\n Elapsed Time={end_of_timer - start_of_timer}\n'
  print("Prepared Subject Line:", msg['Subject'])
  msg.set_content(msgbody)
  msg.set_content(msgbody)
  try:
    with smtplib.SMTP(configs['SMTPServerAddress'], timeout=15) as s:
      s.send_message(msg)
      print(f"🟢 Message sent successfully.")
  except smtplib.SMTPRecipientsRefused as e:
      print(f"🔴 Error: All recipients were refused. Details: {e}")
        
  except smtplib.SMTPSenderRefused as e:
      print(f"🔴 Error: The sender address was refused. Details: {e}")
        
  except smtplib.SMTPDataError as e:
      print(f"🔴 Error: The server replied with an unexpected error code. Details: {e}")
        
  except socket.gaierror as e:
      print(f"🔴 Connection Error: Could not resolve the server address '{configs['SMTPServerAddress']}'. Details: {e}")

  except ConnectionRefusedError as e:
      print(f"🔴 Connection Error: The server actively refused the connection. Details: {e}")
        
  except smtplib.SMTPException as e:
      # This is the base class for all smtplib errors. It acts as a catch-all 
      # for any SMTP issues not explicitly caught above.
      print(f"🔴 General SMTP Error: {e}")

  except Exception as e:
      # Catch-all for non-SMTP errors (e.g., your internet goes down entirely)
      print(f"🔴 An unexpected system error occurred: {e}")
  thelogger.info('CheckArchivedIfSuspended->Sent Status message')
  thelogger.info(f'CheckArchivedIfSuspended->Done!! - Took {end_of_timer - start_of_timer}')
  print('Done!!!')