import pandas as pd
import os, sys, shlex, subprocess, json, logging, smtplib, datetime
from sqlalchemy.engine import URL
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pathlib import Path
from timeit import default_timer as timer
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from collections.abc import Iterable

"""
Docstring for FlaskApps.aeriesstudentchange.aeriesstuchange



DECLARE @NEW_LAST_ID INT = (SELECT ID FROM LOC WHERE CD = @SITE) + 1
"""


def change_student_id(old_student_id, site):
    CONFIG_PATH = os.environ.get('CONFIG_PATH', '/app/config/Acalanes.json')
    try:
        with open(CONFIG_PATH) as f:
            configs = json.load(f)
    except Exception as e:
        print(f"CRITICAL: Could not load config file at {CONFIG_PATH}: {e}")
        configs = {}

    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = "edannewitz@auhsdschools.org"
    msgbody = ''
    msgbody = 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
    msgbody += f"Using Database->{configs['AERIESDatabase']}\n"

    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    query = text("SELECT ID FROM LOC WHERE CD = :site")
    try:
        # 2. Execute the query
        df = pd.read_sql_query(query, engine, params={"site": site_code})
        # 3. Check for "No Rows Returned"
        if df.empty:
            print(f"Warning: No rows found for site code: {site_code}")
            return None   
        # 4. Check for Nulls in specific columns
        if df['ID'].isnull().all():
            print("Notice: Rows found, but all ID values are NULL.")
        return df
    except SQLAlchemyError as e:
        # 5. Catch SQL-specific errors (Syntax, Connection, etc.)
        print(f"Database Error: {e}")
        return None
    except Exception as e:
        # Catch unexpected Python errors
        print(f"An unexpected error occurred: {e}")
        return None



    get_last_id_query = """SELECT ID FROM LOC WHERE CD = {site}"""
    aeriesSQLData = pd.read_sql_query(get_last_id_query, engine)
    last_id = aeriesSQLData.iloc[0]['ID']
    new_last_id = last_id + 1
    query1 = """UPDATE LOC SET ID = {new_last_id} WHERE CD = {site}"""
    query2 = """UPDATE IDN SET ID = {new_last_id} WHERE ID = {old_student_id}"""
    query3 = """UPDATE PWA SET PID = {new_last_id} WHERE PID = {old_student_id}"""
    query4 = """UPDATE PWS SET ID = {new_last_id} WHERE ID = {old_student_id}"""
    query5 = """UPDATE TECH SET BID = {new_last_id} WHERE BID = {old_student_id}"""
    queryresult1 = pd.read_sql_query(query1, engine)
    queryresult2 = pd.read_sql_query(query2, engine)
    queryresult3 = pd.read_sql_query(query3, engine)
    queryresult4 = pd.read_sql_query(query4, engine)
    queryresult5 = pd.read_sql_query(query5, engine)

    return new_last_id
