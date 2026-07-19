import pandas as pd
from sqlalchemy import create_engine, URL
from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
from logging.handlers import SysLogHandler
from pathlib import Path
import json, logging, os
import time


"""
Python 3.14 Script to go through Active Directory, then compare it to students that are actively enrolled in AERIES and
find students who are NOT in Active Directory


"""

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

def get_engine(configs):
    """Creates and returns the SQLAlchemy engine."""
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsernameE'] + ";PWD=" + configs['AERIESPasswordE'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    return create_engine(connection_url)

def get_aeries_dataframe(configs):
    """Fetches active students from Aeries into a DataFrame using SQLAlchemy."""
    query = """
        SELECT 
            CAST(ID AS VARCHAR) AS STUID, 
            SEM AS EMAIL,
            CONCAT(FN, ' ',LN) AS DisplayName, 
            FN AS FirstName, 
            LN AS LastName,
            SC AS SchoolCode,
            GR AS Grade,
            NID AS Password             
        FROM STU 
        WHERE DEL = 0 AND TG = ''
    """
    
    try:
        # Utilize the new get_engine function
        engine = get_engine(configs)
        
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
    """Fetches ALL AD student accounts across multiple pages and returns a Pandas DataFrame."""
    server = Server(ldap_config['server'], get_info=ALL)
    conn = Connection(
        server, 
        user=ldap_config['user'], 
        password=ldap_config['password'], 
        authentication=NTLM, 
        auto_bind=True
    )
    
    print("Initiating paged search to bypass the 1000-user limit...")
    
    entry_generator = conn.extend.standard.paged_search(
        search_base=ldap_config['search_base'],
        search_filter='(&(objectCategory=person)(objectClass=user))',
        search_scope=SUBTREE,
        attributes=['sAMAccountName'],
        paged_size=1000,
        generator=True
    )
    
    ad_records = []
    
    for entry in entry_generator:
        if entry.get('type') == 'searchResEntry':
            # Extract attributes dictionary
            attrs = entry.get('attributes', {})
            
            # Force all dictionary keys to lowercase to avoid case-sensitivity bugs
            lower_attrs = {k.lower(): v for k, v in attrs.items()}
            
            if 'samaccountname' in lower_attrs and lower_attrs['samaccountname']:
                sam = lower_attrs['samaccountname']
                sam_value = sam[0] if isinstance(sam, list) else sam
                ad_records.append({'SamAccountName': str(sam_value).strip()})
                
    conn.unbind()
    return pd.DataFrame(ad_records)

def compare_aeries_to_ad_pandas(configs, ldap_config, output_csv):
    """Main module function orchestrating the comparison."""
    print("Fetching active students from Aeries...")
    aeries_df = get_aeries_dataframe(configs)
    
    if aeries_df.empty:
        print("No Aeries data returned. Exiting.")
        return
        
    print(f"Found {len(aeries_df)} active students in Aeries.")
    
    print("Fetching student accounts from Active Directory...")
    ad_df = get_ad_dataframe(ldap_config)
    
    if ad_df.empty:
        print("No AD data returned. Exiting.")
        return
        
    print(f"Found {len(ad_df)} student IDs in AD.")

    print("\n--- AGGRESSIVE DATA CLEANING ---")
    # 1. Force lowercase
    # 2. Strip any weird whitespace
    # 3. Remove accidental ".0" float artifacts that Pandas sometimes adds
    aeries_df['StudentID_Clean'] = aeries_df['STUID'].astype(str).str.lower().str.strip().str.replace(r'\.0$', '', regex=True)
    ad_df['SamAccountName_Clean'] = ad_df['SamAccountName'].astype(str).str.lower().str.strip().str.replace(r'\.0$', '', regex=True)

    # Let's print a side-by-side sample so you can visually verify what is happening
    print("\nSample Aeries ID  |  Sample AD SamAccountName")
    print("------------------|--------------------------")
    for a, d in zip(aeries_df['StudentID_Clean'].head(5), ad_df['SamAccountName_Clean'].head(5)):
        print(f"{a:<17} |  {d}")
    print("---------------------------------------------\n")
    ad_df.to_csv('ad_output.csv',index=False,encoding='utf-8')
    print("Comparing DataFrames...")
    # Find Aeries students whose CLEANED StudentID is NOT IN the CLEANED AD SamAccountName column
    missing_mask = ~aeries_df['StudentID_Clean'].isin(ad_df['SamAccountName_Clean'])
    missing_students_df = aeries_df[missing_mask].copy()
    
    # Drop the temporary clean column before exporting so your CSV stays neat
    missing_students_df = missing_students_df.drop(columns=['StudentID_Clean'])
    
    if not missing_students_df.empty:
        print(f"Found {len(missing_students_df)} active students missing from AD.")
        missing_students_df.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"Exported missing students to: {output_csv}")
    else:
        print("All active Aeries students are present in Active Directory.")
        
    return missing_students_df

if __name__ == "__main__":
    start_time = time.time()
    configs, thelogger = setup_environment()
    os.chdir(configs['PythonTempDirectory'])
    output_dir = "C:\\Users\\Public\\PythonTemp"
    
    LDAP_CONFIG = {
        'server': configs['AD_STU_Server'],
        # HARDCODING the search base here to ensure it searches the student domain
        'search_base': 'OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us',
        'user': 'AUHSD\\tech', # Matched capitalization from the working test script
        'password': configs['ADPassword']
    }
    
    OUTPUT_FILE = 'StudentsMissingInAD_SQLAlchemy.csv'
    
    compare_aeries_to_ad_pandas(configs, LDAP_CONFIG, OUTPUT_FILE)