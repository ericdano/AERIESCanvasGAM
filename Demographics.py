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
 Python 3.14 script to pull data from AERIES and to send it Care/Solace.
 Uses a .JSON file specified in confighome which has a logserveraddress, ssh hostkey, and the login info for CareSolace.
"""

if __name__ == '__main__':
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    keyspath = Path.home() / ".Acalanes" / "hostkeys.txt"
    with open(confighome) as f:
        configs = json.load(f)

    logger = logging.getLogger('CareSolace Demographics')
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    syslog_handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    formatter = logging.Formatter('%(name)s: %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    syslog_handler.setFormatter(formatter)
    logger.addHandler(syslog_handler)
    logger.addHandler(console_handler)

    #prep status (msg) email
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['SendInfoEmailAddr']
    msgbody = ''
    WasThereAnError = False

    server = 'securetransfer.caresolace.com'
    user = configs['CareSolaceUser']
    passwd = configs['CareSolacePW']
    dest_filename_demo = "CARE_SOLACE_DEMOGRAPHICS.csv"
    dest_filename_staff = "CARE_SOLACE_STAFF.csv"
    logger.info('Starting Care/Solace Script')
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'

    # Get AERIES Data
    os.chdir(configs['PythonTempDirectory'])
    logger.info('Connecting To AERIES to get ALL students Data')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    
    """
    Old Query
WITH CTE1 AS (SELECT * FROM COD WHERE TC = 'STU' AND FC = 'HL'),
        CTE2 AS (SELECT * FROM COD WHERE TC = 'STU' AND FC = 'RC1')
    SELECT
        S.ID AS 'Student ID',
        S.FN AS 'First Name',
        S.MN AS 'Middle Name',
        S.LN AS 'Last Name',
        S.GR AS 'Grade Level',
        CASE
          WHEN S.SC IN (7, 30) THEN 6
          ELSE S.SC
        END AS 'School Site',
        S.FNA AS 'Preferred Name',
        S.CID AS 'State Student ID (SSID)',
        CONVERT(char(10), S.BD, 101) AS 'Data of Birth',
        S.SX AS 'Gender',
        '' AS 'Pronouns',
        S.ETH AS 'Hispanic?',
        S.RC1 AS 'Ethnicity',
        CTE1.DE AS 'Preferred Language',
        CTE2.DE AS 'Ethnicity'
    FROM STU S
    INNER JOIN CTE1 ON S.HL = CTE1.CD
    INNER JOIN CTE2 ON S.RC1 = CTE2.CD
    WHERE S.TG = '' AND S.DEL = 0 AND (S.SC = 30 OR S.SC < 8)
    
    """
    QueryDemo = f"""
    WITH COD_HL AS (SELECT CD, DE
        FROM COD
        WHERE TC = 'STU' AND FC = 'HL'),
    COD_RC1 AS (SELECT CD, DE
        FROM COD
        WHERE TC = 'STU' AND FC = 'RC1')
    SELECT
        S.ID AS 'Student ID',
        S.FN AS 'First Name',
        S.MN AS 'Middle Name',
        S.LN AS 'Last Name',
        S.GR AS 'Grade Level',
        S.SC AS 'School Site',
        S.FNA AS 'Preferred Name',
        S.CID AS 'State Student ID (SSID)',
        CONVERT(char(10), S.BD, 101) AS 'Date of Birth',
        S.SX AS 'Gender',
        '' AS 'Pronouns',
        S.ETH AS 'Hispanic?',
        S.RC1 AS 'Ethnicity',
        HL.DE AS 'Preferred Language',
        RC1.DE AS 'Ethnicity'
    FROM STU S
    INNER JOIN COD_HL HL ON S.HL = HL.CD
    INNER JOIN COD_RC1 RC1 ON S.RC1 = RC1.CD
    WHERE S.TG = ''
        AND S.DEL = 0
        AND (S.SC = 30 OR S.SC < 8)
        AND S.SP <> '2'
    OR (S.GR = 8 AND S.SP = '2');
    """
    QueryStaff = f"""
    SELECT FN AS 'First name',
        LN as 'Last name',
        EM as 'Staff Email',
        '' as 'Phone number',
        CO as 'Role/Title',
        PSC as 'Primary School site'
    FROM STF
    WHERE FN > '' 
        AND 'BY' > '0' 
        AND EM > '' 
        AND TG = '' 
        AND DEL = 0 
        AND TI LIKE '%CERTIFICATED%' 
        AND (PSC <> 0 AND PSC <> 30 AND PSC <> 7 AND PSC <> 6)
        AND (CO <> '' AND CO NOT LIKE '%SUB%' AND CO NOT LIKE '%ASSISTANT%')
    ORDER BY PSC
    """

    sql_query_demo = pd.read_sql_query(QueryDemo, engine)
    #print(sql_query_demo)
    sql_query_staff = pd.read_sql_query(QueryStaff,engine)
    #print(sql_query_staff)
 
    sql_query_demo.to_csv(dest_filename_demo, index = False)
    sql_query_staff.to_csv(dest_filename_staff, index = False)
    logger.info('Wrote temp CSV to disk')
    msgbody += f"Got AERIES data, connecting to FTPS\n"
    logger.info('Connecting to Care/Solaces via FTPS')
    hostkeys = paramiko.hostkeys.HostKeys(filename=keyspath)
    hostFingerprint = hostkeys.lookup(server)['ssh-rsa']
    try:
        tp = paramiko.Transport(server,22)
        tp.connect(username = user, password = passwd, hostkey=hostFingerprint)
        logger.info('Connected to FTPS')
        fileToUpload = {"CARE_SOLACE_DEMOGRAPHICS.csv":"CARE_SOLACE_DEMOGRAPHICS.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        logger.info('Uploading Students')
        for key, value in fileToUpload.items():
            try:  
                sftpClient.put(key, value)
                print("[" + key + "] successfully uploaded to [" + value + "]")
                logger.info("[" + key + "] successfully uploaded to [" + value + "]")
                msgbody += "[" + key + "] successfully uploaded to [" + value + "]\n"
            except PermissionError as err:
                print(f"SFTP Operation Failed on {key} due to a permissions error on the remote server [{err}]")
                logger.error(f"SFTP Operation Failed on [{key}] due to a permissions error on the remote server [{err}]")
                msgbody += f"SFTP Operation Failed on {key} due to a permissions error on the remote server [{err}\n"
                WasThereAnError = True
            except Exception as err:
                print(f"SFTP failed due to error [{err}")
                logger.error(f"SFTP failed due to error [{err}]")
                msgbody += f"SFTP failed due to error [{err}]\n"
                WasThereAnError = True

        # Staff Upload------------------------

        fileToUploadstaff = {"CARE_SOLACE_STAFF.csv":"CARE_SOLACE_STAFF.csv"}
        sftpClient = paramiko.SFTPClient.from_transport(tp)
        logger.info('Update CareSolace Staff->Uploading Staff')
        for key, value in fileToUploadstaff.items():
            try:  
                sftpClient.put(key, value)
                print(f"[{key}] successfully uploaded to [{value}]")
                logger.info(f"[{key}] successfully uploaded to [{value}]")
                msgbody += f"[{key}] successfully uploaded to [{value}]\n"
            except PermissionError as err:
                print(f"SFTP Operation Failed on [{key}] due to a permissions error on the remote server [{err}]")
                logger.error(f"SFTP Operation Failed on [{key}] due to a permissions error on the remote server [{err}]")
                msgbody += f"SFTP Operation Failed on [{key}] due to a permissions error on the remote server [{err}\n"
                WasThereAnError = True
            except Exception as err:
                print("SFTP failed due to error [" + str(err) + "]")
                logger.error(f"SFTP failed due to error [{err}]")
                msgbody += f"SFTP failed due to error {err}]\n"
                WasThereAnError = True
    # Catch errors and log and email them
    except paramiko.ssh_exception.AuthenticationException as err:
        print (f"Can't connect due to authentication error [{err}]")
        logger.error(f"Can't connect due to authentication error [{err}]")
        msgbody +=f"Can't connect due to authentication error [{err}]"
        WasThereAnError = True
    except Exception as err:
        print (f"Can't connect due to other error [{err}]")
        logger.error(f"Can't connect due to other error [{err}]")
        msgbody +=f"Can't connect due to other error [{err}]"
        WasThereAnError = True
    try:
        remote_dir = "/"
        files = sftpClient.listdir(remote_dir)
        print(f"Contents of '{remote_dir}':")
        for file in files:
            print(file)
    except FileNotFoundError:
        print(f"Directory '{remote_dir}' not found.")
        logger.error(f"Directory '{remote_dir}' not found.")
        msgbody += f"Directory '{remote_dir}' not found.\n"
    sftpClient.close()
    tp.close()
    logger.info('Removing CSV files')
    DontDelete = False
    if not(DontDelete):
        os.remove(dest_filename_staff)
        os.remove(dest_filename_demo)
    msgbody += f"""{len(sql_query_demo.index)} student demographics in file uploaded.\n{len(sql_query_staff.index)} staff demographics in file uploaded.\n"""
    logger.info('Care/Solace->Closed FTP and deleted temp CSV')
    if WasThereAnError:
        msg['Subject'] = f"""🔴 ERROR! {configs['SMTPStatusMessage']} Care/Solace {datetime.datetime.now():%I:%M%p on %B %d, %Y}"""
    else:
        msg['Subject'] = f"""🟢 {configs['SMTPStatusMessage']} Care/Solace {datetime.datetime.now():%I:%M%p on %B %d, %Y}"""
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    logger.info('Done!')