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
 Python 3.11+ script to pull data from AERIES and to send it to Maia Learning.

 Uses a .JSON file specified in confighome which has a logserveraddress, and the login info for Maia Learning.
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
    dest_filename_parents = "maialearning_acalanes_parents.csv"
    dest_filename_gpa = "Acalanes_Maia_GPA.csv"
    dest_filename_stucouns = "maialearning_acalanes_studentcounselors.csv"

    thelogger.info('Update Maia Learning->Starting Maia Learning Script')
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
    #prep status (msg) email
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['MaiaInfoEmailAddr']

    WasThereAnError = False
    # Get AERIES Data
    os.chdir('E:\\PythonTemp')
    # connection_string = "DRIVER={SQL Server};SERVER=SATURN;DATABASE=DST22000AUHSD;Trusted_Connection=yes"
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)

    sql_query = pd.read_sql_query("""SELECT ALTSCN.ALTSC AS School_ID, STU.ID AS StudentID, STU.SEM AS Email, STU.FN AS FirstName, STU.MN AS MiddleName, STU.LN AS LastName, STU.FNA AS NickName, LEFT(CONVERT(VARCHAR, STU.BD, 101), 5) + RIGHT(CONVERT(VARCHAR, STU.BD, 101), 5) AS DateOfBirth, STU.SX AS Gender, STU.GR AS Grade, TECH.GYR AS Classof, STU.AD AS Address1, '' AS Address2, STU.CY AS City, STU.ST AS State, STU.ZC AS Zipcode, '' AS Country, '' AS Citizenship, '' AS EnrollmentEndDate, '' AS Telephone, '' AS FAFSA, '' AS Race, '' AS Ethnicity, TCH.EM AS AssignedCounselor FROM STU INNER JOIN TECH ON STU.SC = TECH.SC AND STU.SN = TECH.SN INNER JOIN ALTSCN ON STU.SC = ALTSCN.SCID INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN WHERE (STU.SC < 8) AND (STU.DEL = 0) AND (STU.TG = '') AND (STU.SP <> '2')""",engine)
    # old query sql_query = pd.read_sql_query("""SELECT ALTSCN.ALTSC AS School_ID, STU.ID as StudentID, STU.SEM as Email, STU.FN AS FirstName, STU.MN AS MiddleName, STU.LN AS LastName, STU.FNA as NickName, LEFT(CONVERT(VARCHAR, STU.BD, 101),5) + RIGHT(CONVERT(VARCHAR, STU.BD, 101), 5) AS DateOfBirth, STU.SX as Gender, STU.GR as Grade, TECH.GYR AS Classof, STU.AD as Address1, '' as Address2, STU.CY as City, STU.ST as State, STU.ZC as Zipcode, '' as Country, '' as Citizenship, '' as EnrollmentEndDate, '' as Telephone, '' as FAFSA, '' as Race, '' as Ethnicity, STU.CU AS AssignedCounselor FROM STU INNER JOIN TECH ON STU.SC = TECH.SC AND STU.SN = TECH.SN INNER JOIN ALTSCN ON STU.SC = ALTSCN.SCID WHERE (STU.SC < 7) AND (STU.DEL = 0) AND (STU.TG = '') AND (STU.SP <> '2') AND STU.ID <> 3006323 AND STU.ID <> 3007723 ORDER BY School_ID, Lastname, Firstname""", engine)
    thelogger.info('Update Maia Learning->Got AERIES data for students')
    # Fix for CEP
    sql_query['School_ID'] = sql_query['School_ID'].replace(['7'],'6')
    #
    sql_query['SchoolID'] = sql_query['School_ID'].apply(change_school_id)
    sql_query.drop(['School_ID'], axis=1, inplace=True)
    first_column = sql_query.pop('SchoolID')
    sql_query.insert(0,'SchoolID',first_column)
    sql_query.to_csv(dest_filename,index=False)
    thelogger.info('Update Maia Learning->Wrote student temp CSV to disk')
    msgbody += "Got AERIES data for Students\n"
    # Now do the staff
    sql_query_staff = pd.read_sql_query("""SELECT PSC AS School_ID, FN AS FirstName, LN AS LastName, EM AS Email, 'Teacher' AS Role, '' AS RoleUpdate FROM STF WHERE DEL = 0 AND TG = '' AND EM > '' AND PSC < 7 AND PSC > 0 AND (TI = 'CERTIFICATED AEA' OR TI = 'Teacher' OR TI = 'Associate Principal' OR TI = 'CERTIFICATED MANAGEMENT')""", engine)
    sql_query_staff['SchoolID'] = sql_query_staff['School_ID'].apply(change_school_id)
    sql_query_staff.drop(['School_ID'], axis=1, inplace=True)
    first_column_staff = sql_query_staff.pop('SchoolID')
    sql_query_staff.insert(0,'SchoolID',first_column_staff)
    sql_query_staff.to_csv(dest_filename_staff,index=False)
    thelogger.info('Update Maia Learning->Wrote staff temp CSV to disk')
    msgbody += "Got AERIES data for Staff\n"
    # Now do the Parents
    sql_query_parents = pd.read_sql_query("""SELECT STU.SC AS School_ID, STU.ID AS StudentId, CON.FN AS FirstName, CON.LN AS LastName, CON.EM AS Email, '' AS PhoneNumber FROM STU INNER JOIN CON ON STU.ID = CON.PID WHERE STU.TG = '' AND STU.DEL = 0 AND STU.SC < 7 AND STU.SP <> '2' AND (CON.CD = 'P1' OR CON.CD = 'P2') AND CON.EM > ''""", engine)
    sql_query_parents['SchoolID'] = sql_query_parents['School_ID'].apply(change_school_id)
    sql_query_parents.drop(['School_ID'], axis=1, inplace=True)
    first_column_parents = sql_query_parents.pop('SchoolID')
    sql_query_parents.insert(0,'SchoolID',first_column_parents)
    sql_query_parents[["RemoveConnection"]]  = ""
    sql_query_parents.to_csv(dest_filename_parents,index=False)
    thelogger.info('Update Maia Learning->Wrote Parents temp CSV to disk')
    msgbody += "Got AERIES data for Parents\n"
    # Now do the GPA
    sql_query_gpa = pd.read_sql_query("""SELECT SC as School_ID, ID AS StudentID, TP AS WGPA, TPN AS CGPA, '' AS 'French BAC', '' AS 'IB Final', '' AS 'IB Predicted' FROM STU WHERE SC < 7 AND DEL = 0 AND TG = '' AND SP <> '2'""", engine)
    sql_query_gpa['SchoolID'] = sql_query_gpa['School_ID'].apply(change_school_id)
    sql_query_gpa.drop(['School_ID'], axis=1, inplace=True)
    first_column_gpa = sql_query_gpa.pop('SchoolID')
    sql_query_gpa.insert(0,'SchoolID',first_column_gpa)
    sql_query_gpa.to_csv(dest_filename_gpa,index=False)
    thelogger.info('Update Maia Learning->Wrote Parents temp CSV to disk')
    msgbody += "Got AERIES data for GPA\n"

    #------------------
    #sql_query_studentcounselors = pd.read_sql_query("""SELECT STU.SC as School_ID, STU.SEM AS 'StudentEmail', TCH.EM AS 'AssignedCounselorEmail' FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN WHERE STU.SC < 8 AND STU.DEL = 0 AND STU.SP <> '2' AND STU.TG = ''""",engine)
    #sql_query_studentcounselors = pd.read_sql_query("""SELECT STU.SC AS 'School_ID', STU.SEM AS 'StudentEmail', TCH.EM AS 'AssignedCounselorEmail' FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN WHERE STU.SC < 7 AND STU.DEL = 0 AND STU.SP <> '2' AND STU.TG = ''""",engine)
    #sql_query_studentcounselors = pd.read_sql_query("""SELECT STU.SEM AS 'StudentEmail', TCH.EM AS 'AssignedCounselorEmail' FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN WHERE STU.SC < 7 AND STU.DEL = 0 AND STU.SP <> '2' AND STU.TG = ''""",engine)

    #sql_query_studentcounselors.to_csv("test.csv",index=False)
    #sql_query_studentcounselors['SchoolID'] = sql_query_studentcounselors['School_ID'].apply(change_school_id)
    #sql_query_studentcounselors.drop(['School_ID'], axis=1, inplace=True)
    #first_column_stucoun = sql_query_studentcounselors.pop('SchoolID')
    #sql_query_studentcounselors.insert(0,'SchoolID',first_column_stucoun)
    #sql_query_studentcounselors.to_csv(dest_filename_stucouns,index=False)
    #thelogger.info('Update Maia Learning->Wrote Students and Counselours temp CSV to disk')
    #msgbody += "Got AERIES data for Student-Counselors\n"   
    #-----------------
    
    thelogger.info('Update Maia Learning->Connecting to Maia Learning via FTPS')
    hostkeys = paramiko.hostkeys.HostKeys(filename=keyspath)
    hostFingerprint = hostkeys.lookup(server)['ssh-rsa']
   
    try:
        tp = paramiko.Transport(server,22)
        tp.connect(username = user, password = passwd, hostkey=hostFingerprint)
        thelogger.info('Update Maia Learning->Connected to FTPS')
        fileToUpload = {"maialearning_acalanes_students.csv":"./student/maialearning_acalanes_students.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        thelogger.info('Update Maia Learning->Uploading Students')
        
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
        # Staff Upload------------------------
        fileToUploadstaff = {"maialearning_acalanes_staff.csv":"./teacher/maialearning_acalanes_staff.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        thelogger.info('Update Maia Learning->Uploading Staff')
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
   
        #Parent Upload--------------------------
        fileToUploadparents = {"maialearning_acalanes_parents.csv":"./parent/maialearning_acalanes_parents.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        thelogger.info('Update Maia Learning->Uploading Parents')
        for key, value in fileToUploadparents.items():
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
       
        #GPA Upload--------------------------
        fileToUploadGPA = {"Acalanes_Maia_GPA.csv":"./gpa/Acalanes_Maia_GPA.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        thelogger.info('Update Maia Learning->Uploading GPA')
        for key, value in fileToUploadGPA.items():
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

        """
        fileToUploadStudentCounselors = {"Acalanes_Maia_GPA.csv":"./students_counselors/Acalanes_Maia_StudentCounselors.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        thelogger.info('Update Maia Learning->Uploading Students and Counselor Relationships')
        for key, value in fileToUploadStudentCounselors.items():
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
        """ 
        # close connection

        
        # -----
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
    thelogger.info('Update Maia Learning->Removing CSV files')
    DontDelete = False
    if not(DontDelete):
        os.remove(dest_filename)
        os.remove(dest_filename_staff)
        os.remove(dest_filename_gpa)
        os.remove(dest_filename_parents)

    msgbody += str(len(sql_query.index)) + ' Student records in file uploaded.\n'
    msgbody += str(len(sql_query_gpa.index)) + ' GPA records in file uploaded.\n'
    msgbody += str(len(sql_query_staff.index)) + ' Staff records in file uploaded.\n'
    msgbody += str(len(sql_query_parents.index)) + ' Parent records in file uploaded.\n'
    #msgbody += str(len(sql_query_studentcounselors.index)) + ' Student-Counselor records in file uploaded.\n'
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
