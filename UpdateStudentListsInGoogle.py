import pandas as pd
import os, sys, shlex, subprocess, gam, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

"""
This script finds counselors and their assigned students in AERIES, then updates Google Groups lists with any student changes
Counselors are the Owners of the list. The GAM commands updates the groups with whatever is in the CSV file
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
    WasThereAnError = False
    DontDeleteFiles = False
    # Change directory to a TEMP Directory where GAM and Python can process CSV files 
    os.chdir('E:\\PythonTemp')
    """
    name of the lists is ahsgrade10students@auhsdschools.org (all at site by grade level)
                         ahsstudents@auhsdschools.org (all at site)
                         students@auhsdschools.org (all in district)
    """
    # site abbr, grade level, site number
    campusabbr = ['ahs','chs','llhs','mhs']
    campuses = [ ('ahs',8,2),
                 ('ahs',9,2),
                 ('ahs',10,2),
                 ('ahs',11,2),
                 ('ahs',12,2),
                 ('chs',8,4),
                 ('chs',9,4),
                 ('chs',10,4),
                 ('chs',11,4),
                 ('chs',12,4),
                 ('llhs',8,1),
                 ('llhs',9,1),
                 ('llhs',10,1),
                 ('llhs',11,1),
                 ('llhs',12,1),
                 ('mhs',8,3),
                 ('mhs',9,3),
                 ('mhs',10,3),
                 ('mhs',11,3),
                 ('mhs',12,3)]

    msgbody += f"Using Database->{configs['AERIESDatabase']}\n"
    os.chdir('E:\\PythonTemp')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    thelogger.info('UpdateStudentListsInGoogle->Connecting To AERIES to get ALL students for Google Lists')
    the_query = f"""
    SELECT
        ID,
        SEM,
        SC,
        GR
    FROM
        STU
    WHERE
        STU.DEL=0
        AND STU.TG = ''
        AND (SC < 8 OR SC = 30)
    """
    students = pd.read_sql_query(the_query,engine)
    # Read ALL the students in and then replace School codes with the campus abbreviations
    students['SC'] = students['SC'].replace({1:'llhs',2:'ahs',3: 'mhs',4: 'chs'})
    students['GR'] = students['GR'].astype(str)
    # Group Dataframe by campus and dump csv files to temp space
    # First dump ALL students to the all CSV
    header = ["SEM"]
    students.to_csv('students.csv', index=False, header=False, columns=header)
    grouped_by_sc = students.groupby('SC')
    for group_name, group_sem in grouped_by_sc:
        print(group_sem)
        print("-" * 30)
        filename = f"{group_name}students.csv"
        header = ["SEM"]
        group_sem.to_csv(filename, index=False, header=False, columns=header)
 
    grouped_by_sc_gr = students.groupby(['SC','GR'])
    for group_name, group_sem in grouped_by_sc_gr:
        filenamepart = "grade".join(str(val).replace(" ","_") for val in group_name)
        print(filenamepart)
        print(group_sem)
        print("-" * 30)
        filename = f"{filenamepart}students.csv"
        header = ["SEM"]
        group_sem.to_csv(filename, index=False, header=False, columns=header)

    gam.initializeLogging()
    """
    Now call gam
    
    name of the lists is ahsgrade10students@auhsdschools.org (all at site by grade level)
                         ahsstudents@auhsdschools.org (all at site)
                         students@auhsdschools.org (all in district)
    """
    # Sync ALL students first
    gamliststring = 'students'
    filenamestring = 'students.csv'
    thelogger.info(f"UpdateStudentListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
    stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
    if stat1 != 0:
        WasThereAnError = True
        thelogger.critical('UpdateStudentListsInGoogle->GAM returned an error for the last command')
    if not DontDeleteFiles:
        try:
            os.remove(filenamestring)
        except:
            msgbody += f"Error removing {campus[0]} ALL grades list.\n" 
            thelogger.critical(f"UpdateStudentListsInGoogle->Error trying to remove file {counselor[1]} ALL Grades list csv")
    msgbody += f"Synced Students-> All list. Gam Status->{stat1}\n" 
    """
    name of the lists is ahsgrade10students@auhsdschools.org (all at site by grade level)
                         ahsstudents@auhsdschools.org (all at site)
                         students@auhsdschools.org (all in district)
    Sync Lists for Students by Grade
    site abbr, grade level, site number

    """
    for campus in campusabbr:
        print(campus)

    
    for campus in campusabbr:
        gamliststring = campus + 'students'
        filenamestring = campus + 'students.csv'
        thelogger.info(f"UpdateStudentListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateStudentListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {campus} ALL grades list.\n" 
                thelogger.critical(f"UpdateStudentListsInGoogle->Error trying to remove file {campus} ALL Grades list csv")
        msgbody += f"Synced {campus} All list. Gam Status->{stat1}\n"     
    exit(0)


    
    #sys.exit()
    for campus in campuses:
        gamliststring = campus[0] + 'grade' + campus[1] + 'students'
        filenamestring = campus[0] + 'grade' + campus[1] + 'students.csv'
        thelogger.info(f"UpdateStudentListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateStudentListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {campus[0]} ALL grades list.\n" 
                thelogger.critical(f"UpdateStudentListsInGoogle->Error trying to remove file {counselor[1]} ALL Grades list csv")
        msgbody += f"Synced {campus[1]} All list. Gam Status->{stat1}\n" 
        # Sync Lists for Grade 9 for counselor
        gamliststring = counselor[0] + counselor[2] + 'grade9counselinglist'
        filenamestring = counselor[0] + "9" + counselor[1] + ".csv"
        thelogger.info(f"UpdateStudentListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateStudentListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]}  9th grade list.\n" 
                thelogger.critical(f"UpdateStudentListsInGoogle->Error trying to remove file {counselor[1]} 9th grade list csv")
        msgbody += f"Synced {counselor[1]} 9th grade list. Gam Status-> {stat1}\n" 
        # Sync Lists for Grade 10 for counselor
        gamliststring = counselor[0] + counselor[2] + "grade10counselinglist"
        filenamestring = counselor[0] + "10" + counselor[1] + ".csv"
        thelogger.info(f"UpdateStudentListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical(f"UpdateStudentListsInGoogle->GAM returned an error for the last command")
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]} 10th grade list.\n"
                thelogger.critical(f"UpdateStudentListsInGoogle->Error trying to remove file {counselor[1]} 10th grade list csv")
        msgbody += f"Synced {counselor[1]} 10th grade list. Gam Status->{stat1}\n"
        # Sync Lists for Grade 11 for counselor
        gamliststring = counselor[0] + counselor[2] + 'grade11counselinglist'
        filenamestring = counselor[0] + "11" + counselor[1] + ".csv"
        thelogger.info(f"UpdateStudentListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateStudentListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]} 11th grade list.\n" 
                thelogger.critical(f"UpdateStudentListsInGoogle->Error trying to remove file {counselor[1]} 11th grade list csv")
        msgbody += f"Synced {counselor[1]} 11th grade list. Gam Status->{stat1}\n" 
        # Sync Lists for Grade 12 for counselor
        gamliststring = counselor[0] + counselor[2] + 'grade12counselinglist'
        filenamestring = counselor[0] + "12" + counselor[1] + ".csv"
        thelogger.info(f"UpdateStudentListsInGoogle->Running GAM for {gamliststring} using {filenamestring}")
        stat1 = gam.CallGAMCommand(['gam','update', 'group', gamliststring, 'sync', 'members', 'file', filenamestring])
        if stat1 != 0:
            WasThereAnError = True
            thelogger.critical('UpdateStudentListsInGoogle->GAM returned an error for the last command')
        if not DontDeleteFiles:
            try:
                os.remove(filenamestring)
            except:
                msgbody += f"Error removing {counselor[1]} 12th grade list.\n" 
                thelogger.critical(f"UpdateStudentListsInGoogle->Error trying to remove file {counselor[1]} 12th grade list csv")
        msgbody += f"Synced {counselor[1]} 12th grade list. Gam Status->{stat1}\n" 
    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AUHSD Counseling Lists to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " AUHSD Counseling Lists to Google Groups " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    thelogger.info('UpdateStudentListsInGoogle->Sent status message')
    thelogger.info('UpdateStudentListsInGoogle->DONE! - took ' + str(end_of_timer - start_of_timer))
    print('Done!!!')

if __name__ == '__main__':
    main()