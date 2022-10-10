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
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    #prep status (msg) email
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['ASBInfoEmailAddr']
    msgbody = ''
    WasThereAnError = False

    server = 'ftp.csmcentral.com'
    user = configs['ASBWorksUser']
    passwd = configs['ASBWorksPassword']
    AERIESDB = configs['AERIESDB']
    dest_filename = "asbworks_acalanes.csv"
    thelogger.info('Update ASB Works->Starting ASB Works Script')


    # Get AERIES Data
    os.chdir('E:\\PythonTemp')
    thelogger.info('Update ASB Works->Connecting To AERIES to get ALL students Data')
    connection_string = "DRIVER={SQL Server};SERVER=SATURN;DATABASE=DST22000AUHSD;Trusted_Connection=yes"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    sql_query = pd.read_sql_query("""SELECT STU.SC AS School, STU.SN AS Student#, STU.ID AS ID#,STU.FN AS 'First Name', STU.MN AS 'Middle Name', STU.LN AS 'Last Name',STU.AD AS 'Mailing Address', STU.CY AS City, STU.ST AS State, STU.ZC AS 'Zip Code', STU.TL AS 'Home Phone',STU.GR AS Grade FROM STU WHERE STU.SC < 5 AND STU.DEL = 0 AND STU.TG = '' AND STU.SP <> '2'""",engine)
    #print(sql_query)
    sql_query['School'].mask(sql_query['School'] == 1,'LLHS1', inplace=True)
    sql_query['School'].mask(sql_query['School'] == 2,'AHS1', inplace=True)
    sql_query['School'].mask(sql_query['School'] == 3,'MHS1', inplace=True)
    sql_query['School'].mask(sql_query['School'] == 4,'CHS1', inplace=True)
    #print(sql_query)
    sql_query.to_csv(dest_filename, index = False)
    thelogger.info('Update ASB Works->Wrote temp CSV to disk')
    msgbody += "Got AERIES data, connecting to FTPS\n"
    thelogger.info('Update ASB Works->Connecting to ASB Works via FTPS')
    ftp = MyFTP_TLS()
    ftp.ssl_version = ssl.PROTOCOL_TLSv1_2
    ftp.connect(server, 21)
    ftp.set_pasv(True)
    ftp.auth()
    ftp.prot_p()
    ftp.login(user, passwd)
    thelogger.info('Update ASB Works->Connected to FTPS')
    #print("Success connection")
    ftp.set_debuglevel(2)
    ftp.encoding = "utf-8"
    #ftp.getwelcome()
    with open(dest_filename,"rb") as file:
        try:
            ftp.storbinary(f"STOR {dest_filename}", file)
            msgbody += "Successfully uploaded CSV to ASB Works\n"
            thelogger.info('Update ASB Works->Uploaded CSV to FTPS')
        except:
            ftp.quit()
            os.remove(dest_filename)
            msgbody += "Error uploading to ASB Works\n"
            WasThereAnError = True
            thelogger.error('Update ASB Works->Error Uploading to FTPS')
    ftp.quit()
    os.remove(dest_filename)
    msgbody += str(len(sql_query.index)) + ' of students in file uploaded.\n'
    thelogger.info('Update ASB Works->Closed FTP and deleted temp CSV')
    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " ASB Works Upload " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " ASB Works Upload " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
