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
 Python 3.11

 AERIES Query
 LIST STU SSS CRS STU.SC STU.CU STU.ID STU.NM STU.NG SSS.CN CRS.CO IF STU.NG # 13 AND STU.SC # 999 AND SSS.CN # NULL
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
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    msg = MIMEMultipart()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['BusinessOfficeNotifications']

    # Get AERIES Data
    os.chdir('E:\\PythonTemp')
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
        STU.SC, 
        STU.CU, 
        STU.ID, 
        CONCAT(STU.LN, ', ', STU.FN) AS NM, 
        STU.NG, 
        SSS.CN, 
        CRS.CO,
        SSS.SE
    FROM STU
    INNER JOIN SSS 
        ON STU.SC = SSS.SC AND STU.SN = SSS.SN AND SSS.DEL = 0
    INNER JOIN CRS 
        ON SSS.CN = CRS.CN AND CRS.DEL = 0
    WHERE 
        STU.DEL = 0
        AND STU.SC <> 999 
        AND STU.NG <> 13 
        AND (SSS.CN IS NOT NULL AND SSS.CN <> '');
    """
    sql_query = pd.read_sql_query(TheQuery, engine)

    # Use Pandas to rename the columns to proper labels
    sql_query = sql_query.rename(columns={
        'SC': 'School Code',
        'CU': 'Counselor',  
        'ID': 'Student ID',
        'NM': 'Student Name',
        'NG': 'Grade Level',
        'CN': 'Course Number',
        'CO': 'Course Title',
        'SE': 'Section Number'
    })

    dest_filename = "Course Requests from AERIES.csv" # this is a temp file, will be delete at end of script
    print(sql_query)
    sql_query.to_csv(dest_filename, index = False)
    target_user = 'ncarpenter'
    google_sheet_id = "12ZAyR1MJkd1xF3Ff9jBDc8LARlmy_Bv_Auy40ttTvMw"
    gam.initializeLogging()
    uploadfilestring = os.path.join("E:\\", "PythonTemp", dest_filename)
    print(uploadfilestring)
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
                                "Course Requests from AERIES"])
    if stat1 != 0:  
        WasThereAnError = True
        print('GAM Error')
        print(stat1)
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
        html_body += f"""<p>AERIES Course Requests ran successfully</p>
                {html_table_first10}
                <p></p>
                <p>{len(sql_query)} records uploaded to spreadsheet</p>
                <p></p>
                <p>Elapsed Time: {timer() - start_of_timer} seconds</p>
            </body>
            </html>
        """
    if WasThereAnError:
        msg['Subject'] = "ERROR! " + str(configs['SMTPStatusMessage'] + " - AERIES Course Requests to Google Sheets " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    else:
        msg['Subject'] = str(configs['SMTPStatusMessage'] + " - AERIES Course Requests to Google Sheets " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    msg.attach(MIMEText(html_body,'html'))
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    print("Done!")
    # remove tempfile when done
    os.remove(dest_filename)
