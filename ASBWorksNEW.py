import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging, socket
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from io import StringIO
from pathlib import Path
from ssl import SSLSocket
import subprocess
from timeit import default_timer as timer
import pandas as pd
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

"""
 Python 3.14 script to pull data from AERIES and to send it to ASB Works.
 Built in support for this is busted in AERIES as of 7/2026
 Is it working now? No clue. This however works.
 Uses a .JSON file specified in confighome which has a logserveraddress, and the login info for ASB Works.
"""

class ReusedSslSocket(ssl.SSLSocket):
    def unwrap(self):
        pass

class MyFTP_TLS(ftplib.FTP_TLS):
    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            # Force session reuse, omit server_hostname to disable SNI
            conn = self.context.wrap_socket(conn, session=self.sock.session)
            conn.__class__ = ReusedSslSocket
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
    # prep status (msg) email
    # info in the JSON file it loads
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
    os.chdir(configs['PythonTempDirectory'])
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
            STU.GR AS Grade,
            STU.SEM AS Email
    FROM STU WHERE
        STU.SC < 5
        AND STU.DEL = 0
        AND STU.TG = ''
        AND STU.SP <> '2'
    """

    sql_query = pd.read_sql_query(TheASBQuery, engine)
    sql_query['School'] = sql_query['School'].replace({1: 'LLHS1', 2: 'AHS1', 3: 'MHS1', 4: 'CHS1'})
    print(sql_query)
    sql_query.to_csv(dest_filename, index = False)
    thelogger.info('Update ASB Works->Wrote temp CSV to disk')
    msgbody += f"Got AERIES data, connecting to FTPS\n"

    thelogger.info('Update ASB Works->Connecting to ASB Works via FTPS')
    
    # 1. Create a secure default context
    #ctx = ssl.create_default_context()
    
    # 2. Load the specific certificate the vendor provided
    # IMPORTANT: Change "csm_cert.pem" to the exact name of the file you downloaded
    #ctx.load_verify_locations(cafile="C:\\Users\\edannewitz\\.Acalanes\\asb_cert.txt")

    # 3. Lock to TLS 1.2 (to prevent the session resumption crashes we fixed earlier)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2

    # 4. Connect and authenticate using our custom session-reusing class
    ftp = MyFTP_TLS(context=ctx)
    ftp.connect(server, 21)
    ftp.login(user, passwd) 
    
    # 5. Server requires Data Channel Protection "Private" (PROT P)
    ftp.prot_p()
    
    # ---------------------------------------------------------
    # 4. THE FIX: Switch to Active Mode (PORT) to bypass firewall drops
    ftp.set_pasv(True)
    # ---------------------------------------------------------
    
    thelogger.info('Update ASB Works->Connected to FTPS')
    print("Success connection")
    ftp.set_debuglevel(2)

    # 5. Upload the file safely
    with open(dest_filename, "rb") as file:
        try:
            ftp.storbinary(f"STOR {dest_filename}", file)
            msgbody += f"Successfully uploaded CSV to ASB Works\n"
            thelogger.info('Update ASB Works->Uploaded CSV to FTPS')
        except Exception as e:
            ftp.close() 
            msgbody += f"Error uploading to ASB Works: {e}\n"
            WasThereAnError = True
            thelogger.error(f'Update ASB Works->Error Uploading to FTPS: {e}')
            
    # 6. Clean up the temp file OUTSIDE the 'with' block
    if os.path.exists(dest_filename):
        os.remove(dest_filename)
        thelogger.info('Update ASB Works->Deleted temp CSV')

    if not WasThereAnError:
        ftp.quit()
        thelogger.info('Update ASB Works->Closed FTP')

    msgbody += f"{len(sql_query.index)} students in file uploaded.\n"

    thelogger.info('Update ASB Works->Closed FTP and deleted temp CSV')
    if WasThereAnError:
        msg['Subject'] = f"🔴 ERROR! {configs['SMTPStatusMessage']} ASB Works Upload {datetime.datetime.now():%I:%M%p on %B %d, %Y}"
    else:
        msg['Subject'] = f"🟢 {configs['SMTPStatusMessage']} ASB Works Upload {datetime.datetime.now():%I:%M%p on %B %d, %Y}"
    end_of_timer = timer()
    msgbody += f"\n\n Elapsed Time={end_of_timer - start_of_timer}\n"
    print("Prepared Subject Line:", msg['Subject'])
    msg.set_content(msgbody)
    try:
        with smtplib.SMTP(configs['SMTPServerAddress'], timeout=15) as s:
            s.send_message(msg)
            print(f"🟢 Message sent successfully.")
    except smtplib.SMTPRecipientsRefused as e:
        print(f"🔴 Error: All recipients were refused. Details: {e}")
        
    except smtplib.SMTPSenderRefused as e:
        print(f"🔴 Error: The sender address was refused. Details: {e}")
        
    except smtplib.SMTPDataError as e:
        print(f"🔴 Error: The server replied with an unexpected error code. Details: {e}")
        
    except socket.gaierror as e:
        print(f"🔴 Connection Error: Could not resolve the server address '{configs['SMTPServerAddress']}'. Details: {e}")

    except ConnectionRefusedError as e:
        print(f"🔴 Connection Error: The server actively refused the connection. Details: {e}")
        
    except smtplib.SMTPException as e:
        # This is the base class for all smtplib errors. It acts as a catch-all 
        # for any SMTP issues not explicitly caught above.
        print(f"🔴 General SMTP Error: {e}")

    except Exception as e:
        # Catch-all for non-SMTP errors (e.g., your internet goes down entirely)
        print(f"🔴 An unexpected system error occurred: {e}")
    # Send email message to people monitoring this script
    # Done
    print('Done!')
