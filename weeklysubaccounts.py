from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from xkcdpass import xkcd_password as xp
import smtplib, datetime, shlex, subprocess, sys, os
import pandas as pd
import pendulum, random, gam, ldap3, logging, json
from logging.handlers import SysLogHandler
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE, SUBTREE
import ldap3, random, string
from pathlib import Path
"""
 Based on a program written for COVID, this program takes 5 substitute accounts across sites, and rotates the passwords for them every week.
 

campuses = [('ahs','jlarsen@auhsdschools.org,potoole@auhsdschools.org,tcatanesi@auhsdschools.org',''),
             ('chs','mhaldeman@auhsdschools.org,aluk@auhsdschools.org,mhall@auhsdschools.org',''),
             ('llhs','tvu@auhsdschools.org,mmcewen@auhsdschools.org',''),
             ('mhs','kharvin,ssilkitis@auhsdschools.org',''),
             ('dv','jdrury@auhsdschools.org,cstanton@auhsdschools.org,sfrance@auhsdschools.org,lheptig@auhsdschools.org',''),
             ('dvtrans','sfrance@auhsdschools.org,lheptig@auhsdschools.org,bbenjamin@auhsdschools.org,mleavitt@auhsdschools.org','')]

"""
def getConfigs():
  # Function to get passwords and API keys for Acalanes Canvas and stuff
  confighome = Path.home() / ".Acalanes" / "Acalanes.json"
  with open(confighome) as f:
    configs = json.load(f)
  return configs

def main():
    global msgbody,thelogger
    configs = getConfigs()
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    thelogger.info('Subaccounts->Connecting to Zeus...')
    # array for sending out emails
    campuses = [('mhs','kharvin@auhsdschools.org,jyee@auhsdschools.org,dwarford@auhsdschools.org'),
                ('chs','mhaldeman@auhsdschools.org,aluk@auhsdschools.org,kharvin@auhsdschools.org'),
                ('ahs','jlarsen@auhsdschools.org,mmcewen@auhsdschools.org,lfinn@auhsdschools.org'),
                ('llhs','rramos@auhsdschools.org,lfinn@auhsdschools.org,mhall@auhsdschools.org'),
                ('dv','mhernandez@auhsdschools.org,bbenjamin@auhsdschools.org,mleavitt@auhsdschools.org,cstanton@auhsdschools.org')]
    
    docontacts = 'fbarre@auhsdschools.org,edannewitz@auhsdschools.org,mrodriguez@auhsdschools.org,bkearney@auhsdschools.org'

    # flip comments to test email without sending to everyone
    """
    campuses = [('mhs','edannewitz@auhsdschools.org'),
                ('chs','edannewitz@auhsdschools.org'),
                ('ahs','edannewitz@auhsdschools.org'),
                ('llhs','edannewitz@auhsdschools.org'),
                ('dv','edannewitz@auhsdschools.org')]
    
    docontacts = 'edannewitz@auhsdschools.org'
    """
    pendulum.week_starts_at(pendulum.MONDAY)
    pendulum.week_ends_at(pendulum.FRIDAY)
    today = pendulum.now().add(days=3)
    start = today.start_of('week')
    end = today.end_of('week')
    theweekof = "for the week of " + start.strftime('%B %d') + " to " + end.strftime('%B %d')
    df = pd.DataFrame(campuses, columns = ['campusname','contacts'])
    wordfile = xp.locate_wordfile('E:\PythonScripts\GuestPasswords.txt')
    mywords = xp.generate_wordlist(wordfile=wordfile,min_length=6,max_length=6)
    for x in df.index:
        msgbodysummary = f"""
        <html>
          <head></head>
          <body>
            <p>Passwords for Substitute Teacher accounts this week are:</p>
            <p><p>
        """
        gam.initializeLogging()
        for i in range(5):
            
            password = xp.generate_xkcdpassword(mywords, delimiter="",numwords=1)
            num1 = random.randint(10,99)
            password = random.choice(string.ascii_uppercase) + password + str(num1)
            theuser = str(df['campusname'][x]) + "substitute" + str(i+1) + "@auhsdschools.org"
            adusername = str(df['campusname'][x]) + "substitute" + str(i+1)
            print(theuser)
            print(password)
            msgbodysummary += f"""
            <p>{theuser}<br>
            Password: {password}</p>
            ---------------------<br>
            <p></p>
            """
            stat = gam.CallGAMCommand(['gam','update','user',theuser,'password',password])
            #Call powershell script to update the password in AD as well
            p = subprocess.Popen(["powershell.exe","E:\\PowerShellScripts\\UpdatePassword.ps1",adusername,password],stdout=sys.stdout)
            p_out, p_err = p.communicate()
            #msgbodysummary+= f"""<p>GAM error status->{stat} AD errors->{p_err}</p>"""
            print(stat)
            print(p_out)
            print(p_err)
            msgbodyindv = f"""
            <html>
              <head></head>
              <body>
                  <p><b>Login for Windows</b></p>
                  <p>STAFF\{adusername}<br>
                  Password: {password}</p>
                  <p></p>
                  <p>-----------------------------</p>
                  <p></p>
                  <p><b>Login for Mac</b></p>
                  <p>Username:{adusername}<br>
                  Password: {password}</p>
                  <p></p>
                  <p>-----------------------------</p>
                  <p></p>
                  <p><b>Login for Google</b></p>
                  <p>Login: {theuser}<br>
                  Password: {password}</p>
              </body>
            </html>
            """
            msgindv = MIMEMultipart()
            msgindv['Subject'] = f"""Password for {theuser} {theweekof}"""
            msgindv['From'] = 'dontreply@auhsdschools.org'
            msgindv['To'] = str(df['contacts'][x] + "," + "edannewitz@auhsdschools.org")
            msgindv.attach(MIMEText(msgbodyindv,'html'))
            try:
              # Using 'with' automatically handles s.quit() even if an error occurs
              with smtplib.SMTP(configs['SMTPServerAddress'], timeout=10) as s:
                  s.send_message(msgindv)
                  print(f"Email sent successfully {msgindv['Subject']}")
            except smtplib.SMTPConnectError:
                print("Error: Could not connect to the SMTP server. Check the address/port.")
            except smtplib.SMTPAuthenticationError:
                print("Error: SMTP Authentication failed. Check your credentials.")
            except Exception as e:
                print(f"An unexpected error occurred while sending email: {e}")

        # Send summary of all campus subaccount passwords here
        msg = MIMEMultipart()
        msg['Subject'] = "Sub Account Passwords for " + df['campusname'][x].upper() + " " + theweekof
        msg['From'] = 'donotreply@auhsdschools.org'
        msg['To'] = str(df['contacts'][x] + "," + docontacts)
        msg.attach(MIMEText(msgbodysummary,'html'))
        try:
          # Using 'with' automatically handles s.quit() even if an error occurs
          with smtplib.SMTP(configs['SMTPServerAddress'], timeout=10) as s:
              s.send_message(msg)
              print(f"Email sent successfully {msg['Subject']}")
        except smtplib.SMTPConnectError:
            print("Error: Could not connect to the SMTP server. Check the address/port.")
        except smtplib.SMTPAuthenticationError:
            print("Error: SMTP Authentication failed. Check your credentials.")
        except Exception as e:
            print(f"An unexpected error occurred while sending email: {e}")
if __name__ == '__main__':
  main()