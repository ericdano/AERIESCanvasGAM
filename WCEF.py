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
 Python 3.14

 AERIES data for WCEF


"""

if __name__ == '__main__':
    start_of_timer = timer()
    config_path = Path.home() / ".Acalanes" / "Acalanes.json"
    try:
        with config_path.open('r', encoding='utf-8') as f:
            configs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading config: {e}")
        configs = {"default_setting": True}
    # Set up some variables for emailing and error checking
    WasThereAnError = False
    logger = logging.getLogger('WCEF')
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    syslog_handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    formatter = logging.Formatter('%(name)s: %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    syslog_handler.setFormatter(formatter)
    logger.addHandler(syslog_handler)
    logger.addHandler(console_handler)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    msg = MIMEMultipart()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['SendInfoEmailAddr']

    # Get AERIES Data
    os.chdir(configs['PythonTempDirectory'])
    # Need to put some error checking in here to account for SQL connect errors
    connection_url = URL.create(
        "mssql+pyodbc",
        username=configs['AERIESUsername'],
        password=configs['AERIESPassword'],
        host=configs['AERIESSQLServer'],
        database=configs['AERIESDatabase'],
        query={"driver": "ODBC Driver 17 for SQL Server"}, # Use the specific driver name
    )

    engine = create_engine(connection_url)
    TheQuery = f"""
SELECT 
    STU.sem AS 'StudentEmail', 
    STU.LN AS 'Last Name',
    STU.FN AS 'First Name',
    STU.GR AS 'Grade',
    CONVERT(VARCHAR(10), STU.ED, 23) AS 'Enter Date',
    STU.AD AS 'Mailing Address',
    STU.CY AS 'City',
    STU.ST AS 'State',
    STU.ZC AS 'Zip Code',
    
    -- Parent 1 Information (Based on Contact Code 'P1')
    C1.LN AS 'Parent 1 Last Name',
    C1.FN AS 'Parent 1 First Name',
    COALESCE(COD1.DE, C1.RL) AS 'Parent 1 Relationship',
    C1.EM AS 'Parent 1 Email',
    C1.TL AS 'Telephone',
    C1.AD AS 'Parent 1 Address',
    C1.CY AS 'Parent 1 City',
    C1.ST AS 'Parent 1 State',
    C1.ZC AS 'Parent 1 Zip Code',
    
    -- Parent 2 Information (Based on Contact Code 'P2')
    C2.LN AS 'Parent 2 Last Name',
    C2.FN AS 'Parent 2 First Name',
    COALESCE(COD2.DE, C2.RL) AS 'Parent 2 Relationship',
    C2.EM AS 'Parent 2 Email',
    C2.TL AS 'Parent 2 Telephone',
    C2.AD AS 'Parent 2 Address',
    C2.CY AS 'Parent 2 City',
    C2.ST AS 'Parent 2 State',
    C2.ZC AS 'Parent 2 Zip Code'

FROM STU

-- Join for Parent 1 using CON.CD = 'P1'
LEFT JOIN CON C1 
    ON STU.ID = C1.PID 
    AND C1.CD = 'P1' 
    AND C1.DEL = 0

-- Join for Parent 2 using CON.CD = 'P2'
LEFT JOIN CON C2 
    ON STU.ID = C2.PID 
    AND C2.CD = 'P2' 
    AND C2.DEL = 0

-- Join COD table for Parent 1 Relationship
LEFT JOIN COD COD1 
    ON COD1.TC = 'CON' 
    AND COD1.FC = 'RL' 
    AND COD1.CD = C1.RL 
    AND COD1.DEL = 0

-- Join COD table for Parent 2 Relationship
LEFT JOIN COD COD2 
    ON COD2.TC = 'CON' 
    AND COD2.FC = 'RL' 
    AND COD2.CD = C2.RL 
    AND COD2.DEL = 0

WHERE STU.DEL = 0 
  AND STU.TG = ''
  AND STU.SC = 1
    """
    sql_query = pd.read_sql_query(TheQuery, engine)
    logger.info("Got SQL data")
    dest_filename = "Orinda ONE from AERIES.csv" # this is a temp file, will be delete at end of script
    print(sql_query)
    sql_query.to_csv(dest_filename, index = False)
    logger.info("wrote csv to temp file")
    target_user = 'edannewitz'
    google_sheet_id = "1iaog3l4t7VMD2dRpPNZER7gZaZxdKeh-ThSDjkxeI-w"
    gam.initializeLogging()
    uploadfilestring = os.path.join(configs['PythonTempDirectory'], dest_filename)
    #now = datetime.now()
    #current_date = now.strftime('%m/%d/%Y')
    logger.info(uploadfilestring)
    logger.info("Sending CSV up to Google Sheet")
    stat1 = gam.CallGAMCommand(['gam',
                                'user',
                                target_user,
                                'update',
                                'drivefile',
                                'id',
                                google_sheet_id,
                                'retainname',
                                'localfile',
                                uploadfilestring,
                                'csvsheet',
                                "Las Lomas Student Contact Info"])
    if stat1 != 0:  
        WasThereAnError = True
        logger.error("GAM Error - {stat1}")
    first_10_rows = sql_query.head(10)
    html_table_first10 = first_10_rows.to_html(index=False, justify='left', classes='red-table')
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
        """
    if WasThereAnError:
        html_body += f"""
            <p>There was an error</p>
            <p>GAM Status:{stat1}</p>
            """
    else:
        html_body += f"""<p>WCEF Info ran successfully against {configs['AERIESDatabase']} Database.</p>
                {html_table_first10}
                <p></p>
                <p>{len(sql_query)} records uploaded to spreadsheet</p>
                <p></p>
                <p>Elapsed Time: {timer() - start_of_timer} seconds</p>
            </body>
            </html>
        """
    if WasThereAnError:
        msg['Subject'] = f"🔴 ERROR! {configs['SMTPStatusMessage']} - WCEF Info to Google Sheets {datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")}"
    else:
        msg['Subject'] = f"🟢 {configs['SMTPStatusMessage']} - WCEF Info to Google Sheets {datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y")}"
    msg.attach(MIMEText(html_body,'html'))
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    logger.info("Sending Email")
    logger.info("Removing Temp file")
    print("Done!")
    # remove tempfile when done
    os.remove(dest_filename)
    logger.info("Done")