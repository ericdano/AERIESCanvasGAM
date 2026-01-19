import pandas as pd
import os, sys, shlex, subprocess, json, logging, smtplib, datetime
from sqlalchemy.engine import URL
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from collections.abc import Iterable

"""
Docstring for FlaskApps.aeriesstudentchange.aeriesstuchange

"""

def change_student_id(old_student_id, site_code):
    # Load configurations
    CONFIG_PATH = os.environ.get('CONFIG_PATH', '/app/config/Acalanes.json')
    try:
        with open(CONFIG_PATH) as f:
            configs = json.load(f)
    except Exception as e:
        print(f"CRITICAL: Could not load config file at {CONFIG_PATH}: {e}")
        configs = {}
    # Prepare email message with log details
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = "edannewitz@auhsdschools.org"
    msgbody = f"Using Database->{configs['AERIESDatabaseSB']}\n"
    # 1. Create database engine
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServerSandbox'] + ";DATABASE=" + configs['AERIESDatabaseSB'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    query = text("SELECT ID FROM LOC WHERE CD = :site_code")
    try:
        # 2. Select the current last id from LOC table
        df = pd.read_sql_query(query, engine, params={"site_code": site_code})
        # 3. Check for "No Rows Returned"
        if df.empty:
            print(f"Warning: No rows found for site code: {site_code}")
            return None   
        # 4. Check for Nulls in specific columns
        if df['ID'].isnull().all():
            print("Notice: Rows found, but all ID values are NULL.")
            msgbody += "Notice: Rows found, but all ID values are NULL.\n"
            exit(1)
        new_last_id = df['ID'].iloc[0] + 1
        msgbody += f"{df.to_html()}\n"
        msgbody += f"New Last ID calculated as: {new_last_id}\n"
    except SQLAlchemyError as e:
        # 5. Catch SQL-specific errors (Syntax, Connection, etc.)
        print(f"Database Error: {e}")
        msgbody += f"Database Error: {e}\n"
        exit(1)
    except Exception as e:
        # Catch unexpected Python errors
        print(f"An unexpected error occurred: {e}")
        msgbody += f"An unexpected error occurred: {e}\n"
        exit(1)
    query2 = text("UPDATE IDN SET ID = :new_last_id WHERE ID = :old_student_id")
    try:
        # Change student ID in IDN table
        df = pd.read_sql_query(query2, engine, params={"new_last_id": new_last_id, "old_student_id": old_student_id})
        # 3. Check for "No Rows Returned"
        if df.empty:
            print(f"Warning: No rows found for old student ID: {old_student_id} with command UPDATE IDN SET ID = :new_last_id WHERE ID = :old_student_id")
            exit(1)  
        # 4. Check for Nulls in specific columns
        if df['ID'].isnull().all():
            print("Notice: Rows found, but all ID values are NULL.")
        msgbody += f"{df.to_html()}\n"
    except SQLAlchemyError as e:
        # 5. Catch SQL-specific errors (Syntax, Connection, etc.)
        print(f"Database Error: {e}")
        msgbody += f"Database Error: {e}\n"
        exit(1)
    except Exception as e:
        # Catch unexpected Python errors
        print(f"An unexpected error occurred: {e}")
        exit(1)       
    query3 = text("UPDATE PWA SET PID = :new_last_id WHERE PID = :old_student_id")
    try:
        # 2. Change student ID in PWA table
        df = pd.read_sql_query(query3, engine, params={"new_last_id": new_last_id, "old_student_id": old_student_id})
        # 3. Check for "No Rows Returned"
        if df.empty:
            print(f"Warning: No rows found for old student ID: {old_student_id} with command UPDATE PWA SET PID = :new_last_id WHERE PID = :old_student_id")
            msgbody += f"Warning: No rows found for old student ID: {old_student_id} with command UPDATE PWA SET PID = :new_last_id WHERE PID = :old_student_id\n"
            exit(1)
        # 4. Check for Nulls in specific columns
        if df['ID'].isnull().all():
            print("Notice: Rows found, but all ID values are NULL.")
            msgbody += "Notice: Rows found, but all ID values are NULL.\n"
            exit(1)
        msgbody += f"{df.to_html()}\n"
    except SQLAlchemyError as e:
        # 5. Catch SQL-specific errors (Syntax, Connection, etc.)
        print(f"Database Error: {e}")
        msgbody += f"Database Error: {e}\n"
        exit(1)
    except Exception as e:
        # Catch unexpected Python errors
        print(f"An unexpected error occurred: {e}")
        msgbody += f"An unexpected error occurred: {e}\n"
        exit(1)  
    query4 = text("UPDATE PWS SET ID = :new_last_id WHERE ID = :old_student_id")
    try:
        # 2. Change student ID in PWS table
        df = pd.read_sql_query(query4, engine, params={"new_last_id": new_last_id, "old_student_id": old_student_id})
        # 3. Check for "No Rows Returned"
        if df.empty:
            print(f"Warning: No rows found for old student ID: {old_student_id} with command UUPDATE PWS SET ID = :new_last_id WHERE ID = :old_student_id")
            msgbody += f"Warning: No rows found for old student ID: {old_student_id} with command UPDATE PWS SET ID = :new_last_id WHERE ID = :old_student_id\n"
            exit(1)   
        # 4. Check for Nulls in specific columns
        if df['ID'].isnull().all():
            print("Notice: Rows found, but all ID values are NULL.")
            msgbody += "Notice: Rows found, but all ID values are NULL.\n"
            exit(1)
        msgbody += f"{df.to_html()}\n"
    except SQLAlchemyError as e:
        # 5. Catch SQL-specific errors (Syntax, Connection, etc.)
        print(f"Database Error: {e}")
        msgbody += f"Database Error: {e}\n"
        exit(1)
    except Exception as e:
        # Catch unexpected Python errors
        print(f"An unexpected error occurred: {e}")
        msgbody += f"An unexpected error occurred: {e}\n"
        exit(1)   
    query5 = text("UPDATE TECH SET BID = :new_last_id WHERE BID = :old_student_id")
    try:
        # 2. Change student ID in TECH table
        df = pd.read_sql_query(query5, engine, params={"new_last_id": new_last_id, "old_student_id": old_student_id})
        # 3. Check for "No Rows Returned"
        if df.empty:
            print(f"Warning: No rows found for old student ID: {old_student_id} with command UPDATE TECH SET BID = :new_last_id WHERE BID = :old_student_id")
            msgbody += f"Warning: No rows found for old student ID: {old_student_id} with command UPDATE TECH SET BID = :new_last_id WHERE BID = :old_student_id\n"
            exit(1)  
        # 4. Check for Nulls in specific columns
        if df['ID'].isnull().all():
            print("Notice: Rows found, but all ID values are NULL.")
            msgbody += "Notice: Rows found, but all ID values are NULL.\n"
            exit(1)
        msgbody += f"{df.to_html()}\n"
    except SQLAlchemyError as e:
        # 5. Catch SQL-specific errors (Syntax, Connection, etc.)
        print(f"Database Error: {e}")
        msgbody += f"Database Error: {e}\n"
        exit(1)
    except Exception as e:
        # Catch unexpected Python errors
        print(f"An unexpected error occurred: {e}")
        msgbody += f"An unexpected error occurred: {e}\n"
        exit(1)    
    msg['Subject'] = f"AERIES Student ID Change Log for Old Student ID:{old_student_id} to New Student ID:{new_last_id} in Site Code:{site_code}"
    msg.set_content(msgbody)
    try:
        with smtplib.SMTP(configs['SMTPServerAddress']) as server:
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")
        exit(1)

if __name__ == '__main__':
    old_student_id = sys.argv[1]
    site_code = sys.argv[2]
    change_student_id(old_student_id, site_code)
    print('Done')