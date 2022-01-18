from email.message import EmailMessage
from xkcdpass import xkcd_password as xp
import smtplib, datetime, shlex, subprocess, sys, os
import pandas as pd
import pendulum, random

#This was a script used during COVID lockdown that would rotate the passwords on guest Zoom Accounts every week, and mail the passwords to the admins and techs at each site
#Not used after the start of the 2021-2022 school year

campuses = [('ahs','tbell@auhsdschools.org,apowers@auhsdschools.org,mplant@auhsdschools.org,jlarsen@auhsdschools.org,potoole@auhsdschools.org,tcatanesi@auhsdschools.org',''),
             ('chs','jwalker@auhsdschools.org,llee@auhsdschools.org,vknight@auhsdschools.org,mhaldeman@auhsdschools.org,aluk@auhsdschools.org,mhall@auhsdschools.org',''),
             ('llhs','tbenson@auhsdschools.org,ageotina@auhsdschools.org,jhernandez@auhsdschools.org,dgranzotto@auhsdschools.org,bchastain@auhsdschools.org,tvu@auhsdschools.org,mmcewen@auhsdschools.org',''),
             ('mhs','jparks@auhsdschools.org,bgiron@auhsdschools.org,saraharris@auhsdschools.org,bcanty@auhsdschools.org,bkearney@auhsdschools.org,ssilkitis@auhsdschools.org',''),
             ('dv','jdrury@auhsdschools.org,cstanton@auhsdschools.org,sfrance@auhsdschools.org,lheptig@auhsdschools.org',''),
             ('dvtrans','sfrance@auhsdschools.org,lheptig@auhsdschools.org,bbenjamin@auhsdschools.org,mleavitt@auhsdschools.org','')]
docontacts = 'abrar@auhsdschools.org,rkahrer@auhsdschools.org,edannewitz@auhsdschools.org,chenriksen@auhsdschools.org'
pendulum.week_starts_at(pendulum.MONDAY)
pendulum.week_ends_at(pendulum.FRIDAY)
today = pendulum.now().add(days=3)
start = today.start_of('week')
end = today.end_of('week')
theweekof = "for the week of " + start.strftime('%B %d') + " to " + end.strftime('%B %d')
df = pd.DataFrame(campuses, columns = ['campusname','contacts','emailbody'])
wordfile = xp.locate_wordfile('E:\PythonScripts\GuestPasswords.txt')
mywords = xp.generate_wordlist(wordfile=wordfile,min_length=6,max_length=6)
for x in df.index:
    msg = EmailMessage()
    df['emailbody'][x] = "Passwords for Guest accounts this week are:\n\n"
    for i in range(5):
        password = xp.generate_xkcdpassword(mywords, delimiter="",numwords=1)
        num1 = random.randint(10,99)
        password = password + str(num1)
        df['emailbody'][x] = df['emailbody'][x] + "Guest user -> " + df['campusname'][x] + "-guest" + str(i+1) + "@auhsdschools.org"  + "     Password -> " + password + "\n\n"
        gamstring = "E:\\GAMADV-XTD3\\gam.exe update user " + df['campusname'][x] + "-guest" + str(i+1) + "@auhsdschools.org password " + password
        p = subprocess.Popen(["powershell.exe",gamstring],stdout=sys.stdout)
        p.communicate()
    s = smtplib.SMTP('10.99.0.202')
    msg['Subject'] = "Guest Account Passwords for " + df['campusname'][x].upper() + " " + theweekof
    msg['From'] = 'donotreply@auhsdschools.org'
    msg['To'] = str(df['contacts'][x] + "," + docontacts)
    msg.set_content(df['emailbody'][x])
    s.send_message(msg)
