import io, ftplib, ssl, sys, os, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from ldap3 import Server, Connection, ALL
from io import StringIO
from pathlib import Path
from timeit import default_timer as timer
import pandas as pd
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

"""
 Python 3.9+
"""

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
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    msg = MIMEMultipart()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = 'edannewitz@auhsdschools.org'
    
    WasThereAnError = False
    thelogger.info('AERIES Scan for New Students->Connecting To AERIESa')
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    NewStudents = f"""
    select * from stu where tg='' and del = 0 and sem = '' and sc < 8
    """
    sql_query = pd.read_sql_query(NewStudents, engine)
    print(sql_query)
    html_table_NewStudents = sql_query.to_html(index=False, justify='left', classes='red-table')
    html_body = f"""
        <html>
        <head>
        <style>
            table {{ 
                border-collapse: collapse; 
                width: 100%; 
                font-family: sans-serif; 
                margin-bottom: 20px;
            }}
            th {{ 
                background-color: #f2f2f2; 
                font-weight: bold; 
                padding: 8px; 
                border: 1px solid #ddd; 
                color: black;
            }}
            td {{ 
                padding: 8px; 
                border: 1px solid #ddd; 
            }}
            
            /* Target only the table with the 'red-table' class */
            .red-table td {{ 
                color: #FF0000; 
            }}
            
            /* Target only the table with the 'black-table' class */
            .black-table td {{ 
                color: #000000; 
            }}
        </style>
        </head>
        <body>
            <p>New Students in AERIES without Emails:</p>
            <p><i>Ran this SQL query:</i> {NewStudents}</p>
            {html_table_NewStudents}
            <p></p>
        """
    if sql_query.empty:
        html_body += f"""<p>There seem to be no new students without emails.</p>
        <p><p>"""
    html_body += f"""
            <p>Elapsed Time: {timer() - start_of_timer} seconds</p>
        </body>
        </html>
    """
    #sql_query.to_csv(dest_filename, index = False)
    #thelogger.info('AERIES Scan for New Students->Wrote temp CSV to disk')
    #thelogger.info('AERIES Scan for New Students->Connecting to ASB Works via FTPS')
    #exit(1)

    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " AERIES New Student Scan " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " AERIES New Student Scan " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    msg.attach(MIMEText(html_body,'html'))
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
