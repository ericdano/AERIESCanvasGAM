import os
import time
from datetime import datetime
from email.mime.text import MIMEText
import json
import urllib.parse
import smtplib
import pandas as pd
import concurrent.futures
from sqlalchemy import create_engine, text
from pathlib import Path

# --- 1. Load Configurations ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
try:
    with open(confighome, 'r') as f:
        configs = json.load(f)
        
    # Email Configs
    SMTP_SERVER = configs.get('SMTPServerAddress', '10.99.0.202')
    SMTP_FROM = configs.get('SMTPAddressFrom', 'donotreply@auhsdschools.org')
    ALERT_EMAIL = configs.get('SendInfoEmailAddr', 'edannewitz@auhsdschools.org')

    # Local DB Configs
    local_server_name = 'AERIESLINK.acalanes.k12.ca.us,30000'
    local_db_name = 'AERIES'
    local_uid = configs.get('LocalAERIES_Username')
    local_db_pwd = configs.get('LocalAERIES_Password')

    # Remote DB Configs
    remote_server_name = configs.get('AERIESSQLServer')
    remote_db_name = configs.get('AERIESDatabase')
    remote_uid = configs.get('AERIESTechDept')
    remote_db_pwd = configs.get('AERIESTechDeptPW')

except Exception as e:
    print(f"Error loading config: {e}")
    exit(1)

# --- 2. Setup Connection Strings & Engines ---
# Source Engine
source_odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={remote_server_name};DATABASE={remote_db_name};UID={remote_uid};PWD={remote_db_pwd};TrustServerCertificate=yes;"
source_params = urllib.parse.quote_plus(source_odbc_str)
source_db_url = f"mssql+pyodbc:///?odbc_connect={source_params}"
source_engine = create_engine(source_db_url)

# Destination Engine (Using fast_executemany for massive speed boost on inserts)
dest_odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={local_server_name};DATABASE={local_db_name};UID={local_uid};PWD={local_db_pwd};TrustServerCertificate=yes;"
dest_params = urllib.parse.quote_plus(dest_odbc_str)
dest_db_url = f"mssql+pyodbc:///?odbc_connect={dest_params}"
dest_engine = create_engine(dest_db_url, fast_executemany=True)

# --- 3. Execute ETL Process ---
try:
    # Extract Data
    print(f"[{datetime.now()}] ⏳ Extracting data from source...")
    query = "SELECT * FROM STU WHERE TG='' AND  DEL=0"
    df = pd.read_sql(query, source_engine)
    print(f"[{datetime.now()}] ✅ Extracted {len(df)} rows.")

    # Truncate Destination Table (keeps schema, wipes data)
    print(f"[{datetime.now()}] 🧹 Truncating local STU table...")
    with dest_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE STU"))

    # Load Data to Destination (Appends to the freshly emptied table)
    print(f"[{datetime.now()}] 💾 Loading data to destination...")
    df.to_sql('STU', dest_engine, if_exists='append', index=False)
    print(f"[{datetime.now()}] 🎉 Transfer Complete!")

    # --- 4. Send Success Notification ---
    body = f"The Aeries STU data refresh to the local MSSQL database has completed successfully.\n\nRecords Transferred: {len(df)}"
    msg = MIMEText(body)
    msg['Subject'] = "Aeries STU Data Refresh Complete"
    msg['From'] = SMTP_FROM
    msg['To'] = ALERT_EMAIL
    
    # Connects to your local unsecured SMTP server on port 25
    with smtplib.SMTP(SMTP_SERVER, 25) as server:
        server.send_message(msg)
    print(f"[{datetime.now()}] 📧 Success email sent to {ALERT_EMAIL}")

except Exception as e:
    print(f"[{datetime.now()}] ⚠️ Error during transfer or email: {e}")