import os, sys, shlex, subprocess, gam, datetime, json, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

"""
 This script is run once a day to make sure students don't have a vacation responder on
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
    thelogger.info('Disable-Student-Vacation-Responder ->Running GAM')
    stat1 = gam.CallGAMCommand(['gam','ou_and_children','/Students','vacation','off'])
#    gamstring2 = "E:\\GAMADV-XTD3\\gam.exe ou_and_children '/Students' vacation off"
    msgbody = f'Turned off vacation responders on STUDENT OU. Gam Status-> {stat1}\n Done!' 

    thelogger.info('Disable-Student-Vacation-Responder ->Done Syncing to Google Groups')
    if stat1 !=0:
        msg['Subject'] = f"🔴 ERROR! {configs['SMTPStatusMessage']} Disable Student Vacation Responder {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"
    else:
        msg['Subject'] = f"🟢 {configs['SMTPStatusMessage']} Disable Student Vacation Responder {datetime.datetime.now().strftime('%I:%M%p on %B %d, %Y')}"
    end_of_timer = timer()
    msgbody += f'\n\n Elapsed Time={end_of_timer - start_of_timer}\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    thelogger.info(f'Disable-Student-Vacation-Responder ->Sent status message')
    thelogger.info(f'Disable-Student-Vacation-Responder ->Done - Took {end_of_timer - start_of_timer}')

if __name__ == '__main__':
  main()