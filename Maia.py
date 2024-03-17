import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging
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


class ReusedSslSocket(SSLSocket):
    def unwrap(self):
        pass

class MyFTP_TLS(ftplib.FTP_TLS):
    #Explicit FTPS, with shared TLS session
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn,
                                            server_hostname=self.host,
                                            session=self.sock.session)  # reuses TLS session            
            conn.__class__ = ReusedSslSocket  # we should not close reused ssl socket when file transfers finish
        return conn, size
    
if __name__ == '__main__':
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    thelogger = logging.getLogger('MyLogger')
    dest_filename = "maia_acalanes.csv"
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    msgbody = ''
    #prep Maia Learning Info
    server = configs['MaialearningURL']
    user = configs['MaialearningUsername']
    passwd = configs['MaialearningPassword']
    dest_filename = "acalanesuhsd_maialearning.csv"
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
    sql_query = pd.read_sql_query("""SELECT ALTSCN.ALTSC AS SchoolID, STU.ID as StudentID, STU.SEM as Email, STU.FN AS FirstName, STU.MN AS MiddleName, STU.LN AS LastName, STU.FNA as NickName, LEFT(CONVERT(VARCHAR, STU.BD, 101),5) + RIGHT(CONVERT(VARCHAR, STU.BD, 101), 5) AS DateOfBirth, STU.SX as Gender, STU.GR as Grade, TECH.GYR AS Classof, STU.AD as Address1, '' as Address2, STU.CY as City, STU.ST as State, STU.ZC as Zipcode, '' as Country, '' as Citizenship, '' as EnrollmentEndDate, '' as Telephone, '' as FAFSA, '' as Race, '' as Ethnicity, STU.CU AS AssignedCounselor FROM STU INNER JOIN TECH ON STU.SC = TECH.SC AND STU.SN = TECH.SN INNER JOIN ALTSCN ON STU.SC = ALTSCN.SCID WHERE (STU.SC < 7) AND (STU.DEL = 0) AND (STU.TG = '') AND (STU.SP <> '2') AND STU.ID <> 3006323 AND STU.ID <> 3007723 ORDER BY Schoolid, Lastname, Firstname""", engine)
    print(sql_query)
    #sql_query.to_csv(dest_filename, index = False)
    thelogger.info('Update Maia Learning->Wrote temp CSV to disk')
    msgbody += "Got AERIES data, connecting to FTPS\n"
    thelogger.info('Update Maia Learning->Connecting to Maia Learning via FTPS')
    print('Update Maia Learning->Connecting to Maia Learning via FTPS')
    #ftp = MyFTP_TLS()
    #ftp.ssl_version = ssl.PROTOCOL_TLSv1_2
    #ftp.connect(server, 22)
    ##ftp.set_pasv(True)
    #ftp.auth()
    #ftp.prot_p()
    #ftp.login(user, passwd)
    ftp = ftplib.FTP(server,user,passwd)
    ftp.encoding = "utf-8"

    thelogger.info('Update Maia Learning->Connected to FTPS')
    print("Success connection")
    ftp.set_debuglevel(2)
    ftp.encoding = "utf-8"
    ftp.getwelcome()
    ftp.cwd(configs['MaialerningDirectory'])
    ftp.dir()
    with open(dest_filename,"rb") as file:
        try:
            ftp.storbinary(f"STOR {dest_filename}", file)
            msgbody += "Successfully uploaded CSV to Maia Learning\n"
            thelogger.info('UpdateMaia Learning->Uploaded CSV to FTPS')
        except:
            ftp.quit()
            os.remove(dest_filename)
            msgbody += "Error uploading to Maia Learning\n"
            WasThereAnError = True
            thelogger.error('Update Maia Learning->Error Uploading to FTPS')
    ftp.quit()
    os.remove(dest_filename)
    msgbody += str(len(sql_query.index)) + ' students in file uploaded.\n'
    thelogger.info('Maia Learning->Closed FTP and deleted temp CSV')
    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " Maia Learning " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " Maia Learning " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    ftp.dir()