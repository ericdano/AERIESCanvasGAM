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

"""
 Python 3.9+ script to pull data from AERIES and to send it to ASB Works.
 Built in support for this is busted in AERIES as of 5/2022
 Uses a .JSON file specified in confighome which has a logserveraddress, and the login info for ASB Works.
"""
def change_school_id(school_id):
    if school_id == '1' or school_id == 1:
        return '060165000035'
    elif school_id == '2' or school_id == 2:
        return '060165000032'
    elif school_id == '3' or school_id == 3:
        return '060165000036'
    elif school_id == '4' or school_id == 4:
        return '060165000033'
    elif school_id == '6' or school_id == 6:
        return '060165010751'
    else:
        return 'error'


    
if __name__ == '__main__':
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    keyspath = Path.home() / ".Acalanes" / "hostkeys.txt"
    with open(confighome) as f:
        configs = json.load(f)
    thelogger = logging.getLogger('MyLogger')
    dest_filename = "maialearning_acalanes_students.csv"
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    msgbody = ''
    #prep Maia Learning Info
    server = configs['MaialearningURL']
    user = configs['MaialearningUsername']
    passwd = configs['MaialearningPassword']
    dest_filename = "maialearning_acalanes_students.csv"
    dest_filename_staff = "maialearning_acalanes_staff.csv"
    thelogger.info('Update Maia Learning->Starting Maia Learning Script')
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
    #prep status (msg) email
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['ASBInfoEmailAddr']

    WasThereAnError = False
    # Get AERIES Data
    os.chdir('E:\\PythonTemp')
    #thelogger.info('Update ASB Works->Connecting To AERIES to get ALL students Data')
    # connection_string = "DRIVER={SQL Server};SERVER=SATURN;DATABASE=DST22000AUHSD;Trusted_Connection=yes"
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    sql_query = pd.read_sql_query("""SELECT ALTSCN.ALTSC AS School_ID, STU.ID as StudentID, STU.SEM as Email, STU.FN AS FirstName, STU.MN AS MiddleName, STU.LN AS LastName, STU.FNA as NickName, LEFT(CONVERT(VARCHAR, STU.BD, 101),5) + RIGHT(CONVERT(VARCHAR, STU.BD, 101), 5) AS DateOfBirth, STU.SX as Gender, STU.GR as Grade, TECH.GYR AS Classof, STU.AD as Address1, '' as Address2, STU.CY as City, STU.ST as State, STU.ZC as Zipcode, '' as Country, '' as Citizenship, '' as EnrollmentEndDate, '' as Telephone, '' as FAFSA, '' as Race, '' as Ethnicity, STU.CU AS AssignedCounselor FROM STU INNER JOIN TECH ON STU.SC = TECH.SC AND STU.SN = TECH.SN INNER JOIN ALTSCN ON STU.SC = ALTSCN.SCID WHERE (STU.SC < 7) AND (STU.DEL = 0) AND (STU.TG = '') AND (STU.SP <> '2') AND STU.ID <> 3006323 AND STU.ID <> 3007723 ORDER BY School_ID, Lastname, Firstname""", engine)
    msgbody += "Got AERIES data for students\n"
    thelogger.info('Update Maia Learning->Got AERIES data for students')
    sql_query['SchoolID'] = sql_query['School_ID'].apply(change_school_id)
    sql_query.drop(['School_ID'], axis=1, inplace=True)
    first_column = sql_query.pop('SchoolID')
    sql_query.insert(0,'SchoolID',first_column)
    sql_query.to_csv(dest_filename,index=False)
    thelogger.info('Update Maia Learning->Wrote student temp CSV to disk')
    # Now do the staff
    sql_query_staff = pd.read_sql_query("""SELECT PSC AS School_ID, FN AS FirstName, LN AS LastName, EM AS Email, 'Teacher' AS Role, '' AS RoleUpdate FROM STF WHERE DEL = 0 AND TG = '' AND EM > '' AND PSC < 7 AND (TI = 'CERTIFICATED AEA' OR TI = 'Teacher')""", engine)
    sql_query_staff['SchoolID'] = sql_query_staff['School_ID'].apply(change_school_id)
    sql_query_staff.drop(['School_ID'], axis=1, inplace=True)
    first_column_staff = sql_query_staff.pop('SchoolID')
    sql_query_staff.insert(0,'SchoolID',first_column_staff)
    sql_query_staff.to_csv(dest_filename_staff,index=False)
    thelogger.info('Update Maia Learning->Wrote staff temp CSV to disk')
    
    msgbody += "Got AERIES data for staff, connecting to FTPS\n"
    thelogger.info('Update Maia Learning->Connecting to Maia Learning via FTPS')
    hostkeys = paramiko.hostkeys.HostKeys(filename=keyspath)
    hostFingerprint = hostkeys.lookup(server)['ssh-rsa']
    '''
    try:
        tp = paramiko.Transport(server,22)
        tp.connect(username = user, password = passwd, hostkey=hostFingerprint)
        thelogger.info('Update Maia Learning->Connected to FTPS')
        fileToUpload = {"maialearning_acalanes_students.csv":"./student/maialearning_acalanes_students.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        for key, value in fileToUpload.items():
            try:  
                sftpClient.put(key, value)
                print("[" + key + "] successfully uploaded to [" + value + "]")
                thelogger.info("[" + key + "] successfully uploaded to [" + value + "]")
                msgbody += "[" + key + "] successfully uploaded to [" + value + "]\n"
            except PermissionError as err:
                print("SFTP Operation Failed on [" + key + "] due to a permissions error on the remote server [" + str(err) + "]")
                thelogger.info("SFTP Operation Failed on [" + key + "] due to a permissions error on the remote server [" + str(err) + "]")
                msgbody += "SFTP Operation Failed on [" + key + "] due to a permissions error on the remote server [" + str(err) + "]\n"
                WasThereAnError = True
            except Exception as err:
                print("SFTP failed due to error [" + str(err) + "]")
                thelogger.info("SFTP failed due to error [" + str(err) + "]")
                msgbody += "SFTP failed due to error [" + str(err) + "]\n"
                WasThereAnError = True
           
        fileToUploadstaff = {"maialearning_acalanes_staff.csv":"./teacher/maialearning_acalanes_staff.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        for key, value in fileToUploadstaff.items():
            try:  
                sftpClient.put(key, value)
                print("[" + key + "] successfully uploaded to [" + value + "]")
                thelogger.info("[" + key + "] successfully uploaded to [" + value + "]")
                msgbody += "[" + key + "] successfully uploaded to [" + value + "]\n"
            except PermissionError as err:
                print("SFTP Operation Failed on [" + key + "] due to a permissions error on the remote server [" + str(err) + "]")
                thelogger.info("SFTP Operation Failed on [" + key + "] due to a permissions error on the remote server [" + str(err) + "]")
                msgbody += "SFTP Operation Failed on [" + key + "] due to a permissions error on the remote server [" + str(err) + "]\n"
                WasThereAnError = True
            except Exception as err:
                print("SFTP failed due to error [" + str(err) + "]")
                thelogger.info("SFTP failed due to error [" + str(err) + "]")
                msgbody += "SFTP failed due to error [" + str(err) + "]\n"
                WasThereAnError = True
        



        sftpClient.close()
        tp.close()
        thelogger.info("Closed SFTP connections")
        msgbody += "Closed SFTP Connections\n"
    except paramiko.ssh_exception.AuthenticationException as err:
        print ("Can't connect due to authentication error [" + str(err) + "]")
        thelogger.info("Can't connect due to authentication error [" + str(err) + "]")
        msgbody +="Can't connect due to authentication error [" + str(err) + "]"
        WasThereAnError = True
    except Exception as err:
        print ("Can't connect due to other error [" + str(err) + "]")
        thelogger.info("Can't connect due to other error [" + str(err) + "]")
        msgbody +="Can't connect due to other error [" + str(err) + "]"
        WasThereAnError = True
    os.remove(dest_filename)
    '''
    msgbody += str(len(sql_query.index)) + ' records in file uploaded.\n'
    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " Maia Learning Upload " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " Maia Learning Upload " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    print('Done!')