import pandas as pd
import os, sys, shlex, subprocess, gam, datetime, json, smtplib, logging
from pathlib import Path
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
import glob
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

"""
This Python Script talks to AERIES, gets students from 5 sites, sorts them by Grade 
and Site, makes CSV files split out by Grade and Site, and then calls
GAM to update student lists with the same name as the csv file name.

Example, ahsgrade10students.csv updates the ahsgrade10students Google group
etc.

Script sends what it does to a logging server, and will also email what it
did or did not do to a set of users as well

2025 by Eric Dannewitz

"""

start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
#Logging
thelogger = logging.getLogger('MyLogger')
thelogger.setLevel(logging.DEBUG)
handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
thelogger.addHandler(handler)
#prep status (msg) email and stuff
msg = EmailMessage()
msg['From'] = configs['SMTPAddressFrom']
msg['To'] = configs['SendInfoEmailAddr']
msgbody = ''
WasThereAnError = False
DontDeleteFiles = False
# Change directory to a TEMP Directory where GAM and Python can process CSV files 
os.chdir('E:\\PythonTemp')
output_dir = "E:\\PythonTemp"
msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
QueryStr = f"""
SELECT
    SEM, 
    GR,
    SC
FROM
    STU
WHERE
    STU.SC IN ('1','2','3','4','6')
    AND DEL=0
    AND TG=''
ORDER BY
    STU.SC,
    STU.GR
"""
# Logging is a good thing
thelogger.info(f"Student Google Group Updater->Gathering all students")
connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)
with engine.begin() as connection:
    thelogger.info('Student Google Group Updater->Connecting to AERIES to get emails')
    df = pd.read_sql_query(QueryStr,connection)
    thelogger.info('Student Google Group Updater>Closed AERIES connection')
print(df)
msgbody += "Connected to AERIES and got all the student email addresses\n"
# Mapping of site numbers to abbrivations of school names
sc_mapping = {
    1: 'llhs',
    2: 'ahs',
    3: 'mhs',
    4: 'chs',
    6: 'cis'
}
#Set up Mapping to translate Site Codes to text
df['SC'] = df['SC'].replace(sc_mapping)
print("Updated DataFrame with 'SC' values replaced:")
print(df.head())
df['GR'] = df['GR'].apply(lambda x: f"grade{x}students")
print("\nUpdated DataFrame with 'GR' values modified:")
print(df.head())
Grouped = df.groupby(['SC','GR'])
print(Grouped)
# We'll create an empty dataframe to hold the filenames for GAM to process.
file_list = pd.DataFrame(columns=['filename','groupname'])
print("Iterating through groups and creating CVS")
for name, group_df in Grouped:
    #    file_name = f"{'_'.join(name).replace(' ', '_')}.csv"
    file_name = f"{''.join(name).replace(' ', '')}.csv"
    group_name = f"{''.join(name).replace(' ', '')}"
    new_row_data = {'filename': file_name,'groupname': group_name}
    file_list = pd.concat([file_list, pd.DataFrame([new_row_data])],ignore_index=True)
    output_path = os.path.join(output_dir, file_name)
    group_df[['SEM']].to_csv(output_path, index=False)
    print(f"Saved {name}")
# All CSV files created
thelogger.info('Student Google Group Updater>Created temp CSV files for GAM to use')
msgbody += "Created temp CSV files for GAM to use\n"
# We created another dataframe containing the csv filenames and the google group name
# and now we use that to call GAM to update the list from the CSV
# we are going to loop through the file_list dataframe which contains the csv filename and the name of the group to update
for row in file_list.itertuples(index=False):
    print(f"filename: {row.filename}, groupname: {row.groupname}")
    thelogger.info(f"Student Google Group Updater>Processing filename: {row.filename}, groupname: {row.groupname}")
    msgbody += f"Processing filename: {row.filename}, groupname: {row.groupname}\n"
    # Call GAM from Python
    #stat1 = gam.CallGAMCommand(['gam','update', 'group', 'f"{row.group_name}"', 'sync', 'members', 'file', 'f"{row.file_name}"'])
    #if stat1 != 0:
        #WasThereAnError = True
        #thelogger.info('Student Google Group Updater->GAM returned an error from last command')
        #msgbody += f"GAM returned an error from last command on {row.group_name} {row.file_name}\n"
    if not DontDeleteFiles:
        # Delete CSV when done
        os.remove(f"{row.filename}")
msgbody+='Done!\n'
thelogger.info('Student Google Group Updater->Done Syncing to Google Groups')
# Now email status report
if WasThereAnError:
    msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " Student Google Group Updater " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
else:
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " Student Google Group Updater " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
end_of_timer = timer()
msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
#msg.set_content(msgbody)
#s = smtplib.SMTP(configs['SMTPServerAddress'])
#s.send_message(msg)
thelogger.info('Student Google Group Updater->Sent status message')
thelogger.info('Student Google Group Updater->Done - Took ' + str(end_of_timer - start_of_timer))
print("\nProcess complete.")
