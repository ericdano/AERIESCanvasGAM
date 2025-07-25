import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging
import fnmatch
import paramiko
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from io import StringIO
from pathlib import Path
from ssl import SSLSocket
from timeit import default_timer as timer
import pandas as pd
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from datetime import datetime

"""
 Python 3.11+ script to pull data from AERIES and to send it Guardian .

 Uses a .JSON file specified in confighome which has a logserveraddress, ssh hostkey, and the login info for CareSolace.

"""

if __name__ == '__main__':
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    keyspath = Path.home() / ".Acalanes" / "hostkeys.txt"
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

    server = '45.56.111.20'
    user = configs['GuardianUserName']
    passwd = configs['GuardianPassword']
    dest_filename_students = "students-" + str(datetime.now().strftime('%Y')) + "-" + str(datetime.now().strftime('%m')) + "-" + str(datetime.now().strftime('%d')) + ".csv"
    dest_filename_employees = "employees-" + str(datetime.now().strftime('%Y')) + "-" + str(datetime.now().strftime('%m')) + "-" + str(datetime.now().strftime('%d')) + ".csv"
    thelogger.info('Update Guardian ->Starting Guardian  Script')
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'

    # Get AERIES Data
    os.chdir('E:\\PythonTemp')
    thelogger.info('Update Guardian ->Connecting To AERIES to get ALL students Data')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
   
    QueryStudent = f"""
    SELECT STU.ID AS STUDENT_NUMBER, STU.FN AS FIRST_NAME, STU.MN AS MIDDLE_NAME, STU.LN AS LAST_NAME,  CONVERT(char(10), STU.BD, 101) AS DATE_OF_BIRTH, STU.SX AS GENDER,
    '' AS IDENTIFIED_GENDER, STU.FNA AS PREFERRED_NAME, '' AS PERSON_TYPE, '' AS PRIVACY_INDICATOR, '' AS ADDITIONAL_ID1, '' AS ADDITIONAL_ID2,
    '' AS CLASS_STATUS, '' AS STUDENT_STATUS, TECH.GYR AS CLASS_YEAR, '' AS MAJOR, '' AS CREDITS_SEMESTER, '' AS CREDITS_CUMULATIVE, '' AS GPA,
    STU.MPH AS MOBILE_PHONE, '' AS MOBILE_PHONE_CARRIER, '' AS OPT_OUT_OF_TEXT, STU.SEM AS CAMPUS_EMAIL, '' AS PERSONAL_EMAIL, '' AS PHOTO_FILE_NAME,
    '' AS PERM_PO_BOX,
    '' AS PERM_PO_BOX_COMBO,
    '' AS ADMIT_TERM,
    '' AS STUDENT_ATHLETE,
    '' AS TEAM_SPORT1,
    '' AS TEAM_SPORT2,
    '' AS TEAM_SPORT3,
    '' AS HOLD1,
    '' AS HOLD2,
    '' AS HOLD3,
    '' AS HOLD4,
    '' AS HOLD5,
    '' AS HOLD6,
    '' AS HOLD7,
    '' AS ETHNICITY,
    '' AS ADDRESS1_TYPE,
    STU.RAD AS ADDRESS1_STREET_LINE_1,
    '' AS ADDRESS1_STREET_LINE_2,
    '' AS ADDRESS1_STREET_LINE_3,
    '' AS ADDRESS1_STREET_LINE_4,
    STU.RCY AS ADDRESS1_CITY,
    STU.RST AS ADDRESS1_STATE_NAME,
    STU.RZC AS ADDRESS1_ZIP,
    '' AS ADDRESS1_COUNTRY,
    STU.TL AS ADDRESS1_PHONE,
    '' AS ADDRESS2_TYPE,
    '' AS ADDRESS2_STREET_LINE_1,
    '' AS ADDRESS2_STREET_LINE_2,
    '' AS ADDRESS2_STREET_LINE_3,
    '' AS ADDRESS2_STREET_LINE_4,
    '' AS ADDRESS2_CITY,
    '' AS ADDRESS2_STATE_NAME,
    '' AS ADDRESS2_ZIP,
    '' AS ADDRESS2_COUNTRY,
    '' AS ADDRESS2_PHONE,
    '' AS ADDRESS3_TYPE,
    '' AS ADDRESS3_STREET_LINE_1,
    '' AS ADDRESS3_STREET_LINE_2,
    '' AS ADDRESS3_STREET_LINE_3,
    '' AS ADDRESS3_STREET_LINE_4,
    '' AS ADDRESS3_CITY,
    '' AS ADDRESS3_STATE_NAME,
    '' AS ADDRESS3_ZIP,
    '' AS ADDRESS3_COUNTRY,
    '' AS ADDRESS3_PHONE,
    '' AS CONTACT1_TYPE,
    '' AS CONTACT1_NAME,
    '' AS CONTACT1_RELATIONSHIP,
    '' AS CONTACT1_HOME_PHONE,
    '' AS CONTACT1_WORK_PHONE,
    '' AS CONTACT1_MOBILE_PHONE,
    '' AS CONTACT1_EMAIL,
    '' AS CONTACT1_STREET,
    '' AS CONTACT1_STREET2,
    '' AS CONTACT1_CITY,
    '' AS CONTACT1_STATE,
    '' AS CONTACT1_ZIP,
    '' AS CONTACT1_COUNTRY,
    '' AS CONTACT2_TYPE,
    '' AS CONTACT2_NAME,
    '' AS CONTACT2_RELATIONSHIP,
    '' AS CONTACT2_HOME_PHONE,
    '' AS CONTACT2_WORK_PHONE,
    '' AS CONTACT2_MOBILE_PHONE,
    '' AS CONTACT2_EMAIL,
    '' AS CONTACT2_STREET,
    '' AS CONTACT2_STREET2,
    '' AS CONTACT2_CITY,
    '' AS CONTACT2_STATE,
    '' AS CONTACT2_ZIP,
    '' AS CONTACT2_COUNTRY,
    '' AS CONTACT3_TYPE,
    '' AS CONTACT3_NAME,
    '' AS CONTACT3_RELATIONSHIP,
    '' AS CONTACT3_HOME_PHONE,
    '' AS CONTACT3_WORK_PHONE,
    '' AS CONTACT3_MOBILE_PHONE,
    '' AS CONTACT3_EMAIL,
    '' AS CONTACT3_STREET,
    '' AS CONTACT3_STREET2,
    '' AS CONTACT3_CITY,
    '' AS CONTACT3_STATE,
    '' AS CONTACT3_ZIP,
    '' AS CONTACT3_COUNTRY,
    '' AS TERM
    FROM  STU INNER JOIN
    TECH ON STU.SC = TECH.SC AND STU.SN = TECH.SN
    WHERE (STU.SC < 8) AND (STU.GR > 8) AND (STU.ID > 700000) AND (STU.TG = '') AND (STU.SP <> '2') AND (STU.DEL <> 1) 
    """
    QueryStaff = f"""
    SELECT ID AS EMPLOYEE_NUMBER,
    FN AS FIRST_NAME,
    MN AS MIDDLE_NAME,
    LN AS LAST_NAME,
    '' AS DATE_OF_BIRTH,
    GN AS GENDER,
    '' AS PERSON_TYPE,
    EM AS CAMPUS_EMAIL,
    TL AS WORK_PHONE,
    CP AS PERSONAL_PHONE,
    '' AS PERSONAL_EMAIL,
    '' AS PHOTO_FILE_NAME,
    '' AS ADDRESS1_STREET_LINE_1,
    '' AS ADDRESS1_STREET_LINE_2,
    '' AS ADDRESS1_CITY,
    '' AS ADDRESS1_STATE_NAME,
    '' AS ADDRESS1_ZIP,
    '' AS ADDRESS1_COUNTRY,
    '' AS ADDRESS2_STREET_LINE_1,
    '' AS ADDRESS2_CITY,
    '' AS ADDRESS2_ZIP,
    '' AS ADDRESS2_COUNTRY,
    '' AS TERM,
    CP AS MOBILE_PHONE,
    '' AS EMPLOYEE_STATUS,
    FNP AS PREFERRED_NAME
    FROM STF WHERE TG = '' AND DEL = 0 AND FN > '' AND EM > ''
    """
    sql_query_student = pd.read_sql_query(QueryStudent, engine)
    #print(sql_query_demo)
    sql_query_staff = pd.read_sql_query(QueryStaff,engine)
    #print(sql_query_staff)
 
    sql_query_student.to_csv(dest_filename_students, index = False)
    sql_query_staff.to_csv(dest_filename_employees, index = False)

    thelogger.info('Guardian ->Wrote temp CSV to disk')
    msgbody += "Got AERIES data, connecting to FTPS\n"
    thelogger.info('Guardian ->Connecting to Guardian s via FTPS')
    #print(server)
    #hostkeys = paramiko.hostkeys.HostKeys(filename=keyspath)
    #print(hostkeys)
    #hostFingerprint = hostkeys.lookup(server)
    #print(hostFingerprint)['ssh-rsa']
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) # AUTO add key
    ssh.connect(hostname=server,username=user, password=passwd)
    sftp = ssh.open_sftp()
    thelogger.info('Update Guardian->Connected to FTPS')
    sftp.put(dest_filename_students,'files/' + dest_filename_students)
    sftp.put(dest_filename_employees,'files/' + dest_filename_employees)
    # Staff Upload------------------------
    #     fileToUploadstaff = {dest_filename_employees:str("files/")+dest_filename_employees}
    thelogger.info('Update Guardian Staff->Uploading Staff')
    thelogger.info('Update Guardian ->Removing CSV files')
    sftp.close()
    ssh.close()
    DontDelete = False
    if not(DontDelete):
        os.remove(dest_filename_employees)
        os.remove(dest_filename_students)
    msgbody += str(len(sql_query_student.index)) + ' students in file uploaded.\n'
    msgbody += str(len(sql_query_staff.index)) + ' staff in file uploaded.\n'
    thelogger.info('Update Guardian ->Closed FTP and deleted temp CSV')
    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " Guardian  " + datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " Guardian  " + datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    print('Done!')
