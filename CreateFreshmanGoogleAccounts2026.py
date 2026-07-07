import pandas as pd
import json
import logging
from logging.handlers import SysLogHandler
from pathlib import Path
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from timeit import default_timer as timer
import multiprocessing
import platform
from gam import initializeLogging, CallGAMCommand

# Assuming GAM is installed in a way that allows this import, 
# as seen in your previous script's headers.
from gam import CallGAMCommand 

def setup_environment():
    """Loads configs and sets up syslog routing."""
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)

    thelogger = logging.getLogger('GoogleAccountCreator')
    thelogger.setLevel(logging.DEBUG)
    
    # Prevent duplicate logging lines if running interactively
    if not thelogger.handlers:
        handler = logging.handlers.SysLogHandler(address=(configs['logserveraddress'], 514))
        thelogger.addHandler(handler)

    return configs, thelogger

def get_ready_students(configs, thelogger):
    """Pulls 9th graders from AERIES who have a generated password."""
    thelogger.info('Querying AERIES for 9th graders with passwords...')
    
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)

    # Using the raw string (r"") to prevent the \S escape sequence warning from earlier
    query = r"""
    SELECT id, sem, fn, ln, NID, STU.SC,
    CASE STU.SC
        WHEN 1 THEN '/Students/LLHS/Freshman'
        WHEN 2 THEN '/Students/AHS/Freshman'
        WHEN 3 THEN '/Students/MHS/Freshman'
        WHEN 4 THEN '/Students/CHS/Freshman'
        WHEN 6 THEN '/Students/CIS/Freshman'
        WHEN 7 THEN '/Students/CENR/Freshman'
        WHEN 30 THEN '/Students/Transition'
        ELSE '/Students/Un Mapped School ABBR'
    END AS ou
    FROM stu
    WHERE STU.DEL = 0 AND gr = 9 AND NID != ''
    """
    
    df = pd.read_sql_query(query, engine)
    return df

def create_google_accounts(df, configs, thelogger):
    """Iterates through the dataframe and uses GAM to create Google accounts."""
    # Fallback to a hardcoded domain if it's not in your JSON file
    success_count = 0
    if platform.system() != 'Linux':
        multiprocessing.freeze_support()
        multiprocessing.set_start_method('spawn')
    initializeLogging()
    for row in df.itertuples(index=True):
        # 1. Clean and format the data
        email = f"{row.sem}"
        fn = str(row.fn).strip()
        ln = str(row.ln).strip()
        password = str(row.NID).strip()
        ou = str(row.ou).strip()

        # 2. Build the GAM command as a list of arguments
        gam_args = [
            "create", "user", email,
            "firstname", fn,
            "lastname", ln,
            "password", password,
            "org", ou
        ]

        # 3. Execute GAM
        try:
            print(f"Attempting to create: {email} in {ou}")
            # CallGAMCommand acts like you typed 'gam create user...' in the terminal
            #CallGAMCommand(gam_args)
            CallGAMCommand(['gam','create','user',email,'firstname',fn,'lastname',ln,'password',password,'ou',ou])
            
            thelogger.info(f"SUCCESS: GAM account created for {email}")
            success_count += 1
            
        except Exception as e:
            thelogger.error(f"FAILED to create GAM account for {email}: {e}")
            print(f"ERROR creating {email}: {e}")

    return success_count

def main():
    start_time = timer()
    configs, thelogger = setup_environment()
    
    thelogger.info("--- Starting 2026 Google Account Creation Process ---")
    
    # 1. Fetch the data
    df_students = get_ready_students(configs, thelogger)
    
    if df_students.empty:
        print("No 9th graders found needing accounts (or missing passwords). Exiting.")
        thelogger.info("No students found. Exiting.")
        return

    print(f"Found {len(df_students)} students ready for Google Account creation.")
    
    # 2. Process the accounts via GAM
    created_count = create_google_accounts(df_students, configs, thelogger)
    
    # 3. Wrap up
    end_time = timer()
    elapsed = round(end_time - start_time, 2)
    thelogger.info(f"--- Finished. Created {created_count} accounts in {elapsed} seconds. ---")
    print(f"\nDone! Successfully created {created_count} accounts in {elapsed} seconds.")

if __name__ == '__main__':
    main()