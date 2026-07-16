import urllib, timer
import pandas as pd
from sqlalchemy import create_engine
from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
from logging.handlers import SysLogHandler
from pathlib import Path
import json, logging

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


def get_aeries_dataframe(sql_config):
    """Fetches active students from Aeries into a DataFrame using SQLAlchemy."""
    
    # 1. Build the raw ODBC connection string (Windows Authentication)
    odbc_str = (
        f"DRIVER={sql_config['driver']};"
        f"SERVER={sql_config['server']};"
        f"DATABASE={sql_config['database']};"
        "Trusted_Connection=yes;"
    )
    
    # 2. URL-encode the string so SQLAlchemy can parse it safely
    quoted_odbc_str = urllib.parse.quote_plus(odbc_str)
    
    # 3. Create the SQLAlchemy Engine URI
    # The dialect is mssql (Microsoft SQL Server) using the pyodbc driver
    engine_uri = f"mssql+pyodbc:///?odbc_connect={quoted_odbc_str}"
    
    query = """
        SELECT 
            CAST(ID AS VARCHAR) AS StudentID, 
            FN AS FirstName, 
            LN AS LastName 
        FROM STU 
        WHERE DEL = 0 AND TG = ''
    """
    
    try:
        # Create the engine
        engine = create_engine(engine_uri)
        
        # Read directly into a DataFrame using the engine
        # Using a context manager ensures the connection is closed immediately
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            
        # Clean up the string columns (trim whitespace)
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            
        return df
        
    except Exception as e:
        print(f"Error connecting to Aeries via SQLAlchemy: {e}")
        return pd.DataFrame()
    finally:
        # Dispose of the engine to free up connection pools
        if 'engine' in locals():
            engine.dispose()

def get_ad_dataframe(ldap_config):
    """Fetches AD student accounts and returns a Pandas DataFrame."""
    server = Server(ldap_config['server'], get_info=ALL)
    conn = Connection(
        server, 
        user=ldap_config['user'], 
        password=ldap_config['password'], 
        authentication=NTLM, 
        auto_bind=True
    )
    
    conn.search(
        search_base=ldap_config['search_base'],
        search_filter='(&(objectCategory=person)(objectClass=user))',
        search_scope=SUBTREE,
        attributes=['employeeID']
    )
    
    ad_records = []
    for entry in conn.entries:
        if 'employeeID' in entry and entry.employeeID.value:
            ad_records.append({'EmployeeID': str(entry.employeeID.value).strip()})
            
    conn.unbind()
    return pd.DataFrame(ad_records)

def compare_aeries_to_ad_pandas(sql_config, ldap_config, output_csv):
    """Main module function orchestrating the comparison."""
    print("Fetching active students from Aeries...")
    aeries_df = get_aeries_dataframe(sql_config)
    print(f"Found {len(aeries_df)} active students in Aeries.")
    
    if aeries_df.empty:
        print("No Aeries data returned. Exiting.")
        return
    
    print("Fetching student accounts from Active Directory...")
    ad_df = get_ad_dataframe(ldap_config)
    print(f"Found {len(ad_df)} student IDs in AD.")
    
    if ad_df.empty:
        print("No AD data returned. Exiting.")
        return

    print("Comparing DataFrames...")
    # Find Aeries students whose StudentID is NOT IN the AD EmployeeID column
    missing_mask = ~aeries_df['StudentID'].isin(ad_df['EmployeeID'])
    missing_students_df = aeries_df[missing_mask]
    
    if not missing_students_df.empty:
        print(f"Found {len(missing_students_df)} active students missing from AD.")
        missing_students_df.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"Exported missing students to: {output_csv}")
    else:
        print("All active Aeries students are present in Active Directory.")
        
    return missing_students_df

if __name__ == "__main__":
    start_time = timer()
    configs, thelogger = setup_environment()
    SQL_CONFIG = {
        'driver': '{ODBC Driver 17 for SQL Server}',
        'server': configs['AERIESSQLServer'],
        'database': configs['AERIESDatabase']
    }
    
    LDAP_CONFIG = {
        'server': configs['AD_STU_Server'],
        'search_base': configs['AD_Search_Base'],
        'user': 'AUHSD\\tech',
        'password': configs['ADPassword']
    }
    
    OUTPUT_FILE = 'StudentsMissingInAD_SQLAlchemy.csv'
    
    compare_aeries_to_ad_pandas(SQL_CONFIG, LDAP_CONFIG, OUTPUT_FILE)