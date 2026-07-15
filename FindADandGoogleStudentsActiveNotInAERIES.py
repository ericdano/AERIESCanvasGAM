import io
import json
import logging
import logging.handlers
from pathlib import Path
from contextlib import redirect_stdout

import pandas as pd
from sqlalchemy import create_engine, URL
from ldap3 import Server, Connection, ALL
import gam 

# ==========================================
# 0. SETUP AND CONFIGURATION
# ==========================================
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

# ==========================================
# 1. GET ACTIVE AERIES STUDENTS (SQLAlchemy)
# ==========================================
def get_aeries_active(engine, logger):
    logger.info("Querying Aeries for active students...")
    
    query = """
        SELECT LOWER(SEM) AS Email 
        FROM STU 
        WHERE TG = '' 
          AND DEL = 0 
          AND SEM IS NOT NULL 
          AND SEM != ''
    """
    
    try:
        df_aeries = pd.read_sql(query, engine)
        return df_aeries
    except Exception as e:
        logger.error(f"SQLAlchemy Aeries Error: {e}")
        return pd.DataFrame(columns=['Email'])

# ==========================================
# 2. GET ACTIVE GOOGLE STUDENTS (GAM)
# ==========================================
def get_google_active(logger, student_ou):
    logger.info("Querying Google via GAM for active students...")
    
    gam_args = [
        'gam', 'print', 'users', 
        'query', f"isSuspended=false orgUnitPath='{student_ou}'"
    ]
    
    output = io.StringIO()
    
    try:
        with redirect_stdout(output):
            gam.CallGAMCommand(gam_args)
    except SystemExit as e:
        if e.code not in [0, None]:
            logger.error(f"GAM Error: Exited with code {e.code}")
            return pd.DataFrame(columns=['Email'])
    except Exception as e:
        logger.error(f"GAM Exception: {e}")
        return pd.DataFrame(columns=['Email'])

    output.seek(0)
    
    try:
        df_google = pd.read_csv(output)
        df_google = df_google[['primaryEmail']].rename(columns={'primaryEmail': 'Email'})
        df_google['Email'] = df_google['Email'].str.lower()
    except pd.errors.EmptyDataError:
        logger.warning("GAM returned no data.")
        return pd.DataFrame(columns=['Email'])
        
    return df_google

# ==========================================
# 3. GET ACTIVE AD STUDENTS (LDAP)
# ==========================================
def get_ad_active(configs, logger):
    logger.info("Querying Active Directory for active students...")
    
    try:
        server = Server(configs['AD_STU_Server'], get_info=ALL)
        conn = Connection(server, user='AUHSD\\tech', password=configs['ADPassword'], auto_bind=True)
        
        ldap_filter = '(&(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'
        
        conn.search(
            search_base=configs['AD_STU_Search_Base'],
            search_filter=ldap_filter,
            attributes=['mail']
        )
        
        ad_emails = [str(entry.mail).lower() for entry in conn.entries if entry.mail]
        conn.unbind()
        
        return pd.DataFrame(ad_emails, columns=['Email'])
    except Exception as e:
        logger.error(f"LDAP Error: {e}")
        return pd.DataFrame(columns=['Email'])

# ==========================================
# 4. EXECUTE AND COMPARE
# ==========================================
if __name__ == "__main__":
    configs, thelogger = setup_environment()
    thelogger.info("Starting Orphaned Account Check")
    
    # Database Connection using URL.create
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    
    # Create the SQLAlchemy engine
    engine = create_engine(connection_url)
    
    # Fetch data
    df_aeries = get_aeries_active(engine, thelogger)
    df_google = get_google_active(thelogger, configs.get('google_student_ou', '/Students'))
    df_ad = get_ad_active(configs, thelogger)
    
    # Compare
    thelogger.info("Comparing directory datasets...")
    df_active_both = pd.merge(df_google, df_ad, on='Email', how='inner')
    df_orphans = df_active_both[~df_active_both['Email'].isin(df_aeries['Email'])]
    
    # Handle Results
    if not df_orphans.empty:
        orphan_count = len(df_orphans)
        thelogger.warning(f"Found {orphan_count} orphaned student accounts.")
        
        export_file = "orphaned_student_accounts.csv"
        df_orphans.to_csv(export_file, index=False)
        thelogger.info(f"Exported orphan list to {export_file}")
    else:
        thelogger.info("No orphaned accounts found. Directories are clean.")
        
    # Clean up engine resources
    engine.dispose()