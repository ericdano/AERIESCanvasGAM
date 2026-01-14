import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging, gam
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
    dest_filename = "asbworks_acalanes.csv"
    thelogger.info('Update ASB Works->Starting ASB Works Script')
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'

    # Get AERIES Data
    os.chdir('E:\\PythonTemp')
    thelogger.info('Update ASB Works->Connecting To AERIES to get ALL students Data')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    TheASBQuery = f"""
    SELECT STU.SC AS School,
            STU.SN AS Student#,
            STU.ID AS ID#,
            STU.FN AS 'First Name',
            STU.MN AS 'Middle Name',
            STU.LN AS 'Last Name',
            STU.AD AS 'Mailing Address',
            STU.CY AS City,
            STU.ST AS State,
            STU.ZC AS 'Zip Code',
            STU.TL AS 'Home Phone',
            STU.GR AS Grade 
    FROM STU WHERE
        STU.SC < 5
        AND STU.DEL = 0
        AND STU.TG = ''
        AND STU.SP <> '2'
    """
    sql_query = pd.read_sql_query(TheASBQuery, engine)
    sql_query['School'].mask(sql_query['School'] == 1,'LLHS1', inplace=True)
    sql_query['School'].mask(sql_query['School'] == 2,'AHS1', inplace=True)
    sql_query['School'].mask(sql_query['School'] == 3,'MHS1', inplace=True)
    sql_query['School'].mask(sql_query['School'] == 4,'CHS1', inplace=True)
    print(sql_query)
    sql_query.to_csv(dest_filename, index = False)
    thelogger.info('Update ASB Works->Wrote temp CSV to disk')
    msgbody += "Got AERIES data, connecting to FTPS\n"
    thelogger.info('Update ASB Works->Connecting to ASB Works via FTPS')
    #exit(1)
    target_user = "edannewitz@auhsdschools.org"
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    sheet_name = f"Data Export - {today_str}"
    stat1 = gam.CallGAMCommand(['gam','user', target_user, 'create','drivefile','drivefilename',sheet_name, 'localfile',dest_filename,'mimetype','gsheet'])
    if stat1 != 0:  
        WasThereAnError = True
        thelogger.info('Update ASB Works->GAM returned an error from last command')
        msgbody += f"GAM returned an error from last command on ASB Works upload\n"
        print('GAM Error')
    os.remove(dest_filename)
    msgbody += str(len(sql_query.index)) + ' students in file uploaded.\n'
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
