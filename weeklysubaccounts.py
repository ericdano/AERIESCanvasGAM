from email.message import EmailMessage
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
             ('mhs','bkearney@auhsdschools.org,ssilkitis@auhsdschools.org',''),
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
    
    campuses = [('mhs','bkearney@auhsdschools.org,jyee@auhsdschools.org,dwarford@auhsdschools.org'),
                ('chs','mhaldeman@auhsdschools.org,aluk@auhsdschools.org,mhall@auhsdschools.org'),
                ('ahs','jlarsen@auhsdschools.org,mmcewen@auhsdschools.org,kharvin@auhsdschools.org'),
                ('llhs','rramos@auhsdschools.org,lfinn@auhsdschools.org,tvu@auhsdschools.org'),
                ('dv','sfrance@auhsdschools.org,mhernandez@auhsdschools.org,bbenjamin@auhsdschools.org,mleavitt@auhsdschools.org,cstanton@auhsdschools.org')]
    
    docontacts = 'fbarre@auhsdschools.org,edannewitz@auhsdschools.org,mrodriguez@auhsdschools.org'
    docontacts2 = 'edannewitz@auhsdschools.org'
    '''
    campuses = [('mhs','edannewitz@auhsdschools.org'),
                ('chs','edannewitz@auhsdschools.org'),
                ('ahs','edannewitz@auhsdschools.org'),
                ('llhs','edannewitz@auhsdschools.org'),
                ('dv','edannewitz@auhsdschools.org')]
    
    docontacts = 'edannewitz@auhsdschools.org'
    '''
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
        msgbody = ''
        msg = EmailMessage()
        msgbody += "Passwords for Substitute Teacher accounts this week are:\n\n"
        gam.initializeLogging()
        for i in range(5):
            msgindv = EmailMessage()
            password = xp.generate_xkcdpassword(mywords, delimiter="",numwords=1)
            num1 = random.randint(10,99)
            password = random.choice(string.ascii_uppercase) + password + str(num1)
            theuser = str(df['campusname'][x]) + "substitute" + str(i+1) + "@auhsdschools.org"
            adusername = str(df['campusname'][x]) + "substitute" + str(i+1)
            print(theuser)
            print(password)
            msgbody+="Substitute Account -> " + theuser + "     Password -> " + password + "\n"
            stat = gam.CallGAMCommand(['gam','update','user',theuser,'password',password])
            #gamstring = "E:\\GAMADV-XTD3\\gam.exe update user " + df['campusname'][x] + "-guest" + str(i+1) + "@auhsdschools.org password " + password
            p = subprocess.Popen(["powershell.exe","E:\\PowerShellScripts\\UpdatePassword.ps1",adusername,password],stdout=sys.stdout)
            p_out, p_err = p.communicate()
            msgbody+= "GAM error status->" + str(stat) + " AD errors->" + str(p_err) + "\n"
            print(stat)
            print(p_out)
            print(p_err)
            s = smtplib.SMTP('10.99.0.202')
            msgindv['Subject'] = "Password for " + theuser + " " + theweekof
            msgindv['From'] = 'dontreply@auhsdschools.org'
            msgindv['To'] = str(df['contacts'][x] + "," + docontacts2)
            msgbody2 = "Login for Windows\n"
            msgbody2 += "STAFF\\" + adusername + "\n"
            msgbody2 += password + "\n"
            msgbody2 += "\n"
            msgbody2 += "\n"
            msgbody2 += "Login for Mac\n"
            msgbody2 += adusername + "\n"
            msgbody2 += password + "\n"
            msgbody2 += "\n"
            msgbody2 += "\n"
            msgbody2 += "Google login and password: " + theuser + "   " + password + "\n"
            msgindv.set_content(msgbody2)
            s.send_message(msgindv)
        s = smtplib.SMTP('10.99.0.202')
        msg['Subject'] = "Sub Account Passwords for " + df['campusname'][x].upper() + " " + theweekof
        msg['From'] = 'donotreply@auhsdschools.org'
        msg['To'] = str(df['contacts'][x] + "," + docontacts)
        msg.set_content(msgbody)
        s.send_message(msg)

if __name__ == '__main__':
  main()