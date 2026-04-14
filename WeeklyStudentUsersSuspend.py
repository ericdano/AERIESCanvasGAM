import pandas as pd
import os, sys, shlex, gam, subprocess, json, logging, smtplib, datetime, socket
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

"""
Python Script to suspend and archive all users in a certain OU
In this case, it suspends and archives all the users in OU Z-Former Students and Former Staff
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
  # Check Z-Former Students
  thelogger.info('WeeklyStudentSuspend->Starting GAM Suspension Check for Z-Former student OU')
  stat = gam.CallGAMCommand(['gam','ou_and_children','/Z-Former Students','update','user','archive','on','suspended','on'])
  if stat != 0:
    msg['Subject'] = f"🔴 ERROR! {configs['SMTPStatusMessage']} Monthly Student and Staff Suspension Script {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"
  else:
    msg['Subject'] = f"🟢 {configs['SMTPStatusMessage']} Monthly Student and Staff Suspension Script {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"
  thelogger.info('WeeklyStudentSuspend->Starting GAM Suspension Check for Former Staff student OU')
  # Check Former Staff now
  stat = gam.CallGAMCommand(['gam','ou_and_children','/Former Staff','update','user','archive','on','suspended','on'])
  if stat != 0:
    msg['Subject'] = f"🔴 ERROR! {configs['SMTPStatusMessage']} Monthly Student and Staff Suspension Script {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"
  else:
    msg['Subject'] = f"🟢 {configs['SMTPStatusMessage']} Monthly Student and Staff Suspension Script {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"

  end_of_timer = timer()
  msgbody += f'\n\n Elapsed Time={end_of_timer - start_of_timer}\n'
  print("Prepared Subject Line:", msg['Subject'])
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
    # Send email message to people monitoring this script
  thelogger.info('WeeklyStudentSuspend->Sent status message')
  thelogger.info(f'WeeklyStudentSuspend->DONE! - took {end_of_timer - start_of_timer}')
  print('Done!!!')
  
if __name__ == '__main__':
  main()