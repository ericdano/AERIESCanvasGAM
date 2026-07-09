import random
import string
import pandas as pd
import os, sys, subprocess, json, logging
from logging.handlers import SysLogHandler
from pathlib import Path
from sqlalchemy.engine import URL
from sqlalchemy import create_engine, text
from timeit import default_timer as timer

# Assuming GAM is installed in a way that allows this import
from gam import CallGAMCommand 

# --- Character Sets & Word Lists ---
VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnprstvw"
REPLACEABLE_LETTERS = "asihle"
SYMBOL_MAP = {'a': '@', 's': '$', 'i': '!', 'l': '!', 'h': '#', 'e': '&'}

OFFENSIVE_WORDS = [
    "fuck", "shit", "damn", "hell", "piss", "crap", "bitch", "bastard",
    "sex", "porn", "anal", "ass", "butt", "tit", "boob", "penis", "dick", 
    "vagina", "cunt", "clit", "balls", "nuts", "jizz", "shaft", "hardon",
    "fag", "gay", "homo", "nigger", "spic", "chink", "kike", "retard",
    "dumb", "stupid", "idiot", "fat", "ugly", "obese", "loser", "hate",
    "kill", "die", "slave", "nazi", "hitler", "nigga", "faggot", "tranny", 
    "dyke", "negro", "whore", "slut", "cock", "tits", "cum", "boner", 
    "twat", "wanker", "prick", "seggs", "unalive", "kys", "stfu", "pwned", 
    "haxor", "n00b", "leets", "freak", "weirdo", "scum", "trash"
]

def create_password():
    """Generates a single, unique password based on the specified rules."""
    while True:
        word = ""
        for i in range(3):
            word += random.choice(CONSONANTS)
            word += random.choice(VOWELS)

        is_offensive = any(bad_word in word for bad_word in OFFENSIVE_WORDS)
        has_replaceable = any(char in word for char in REPLACEABLE_LETTERS)

        if not is_offensive and has_replaceable:
            replaceable_chars = [char for char in word if char in REPLACEABLE_LETTERS]
            char_to_replace = random.choice(replaceable_chars)
            symbol = SYMBOL_MAP[char_to_replace]
            word_with_symbol = word.replace(char_to_replace, symbol, 1)
            final_word = word_with_symbol.capitalize()
            three_digits = f"{random.randint(0, 999):03d}"
            return final_word + three_digits

def setup_environment():
    """Loads configs and sets up syslog routing."""
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)

    thelogger = logging.getLogger('GoogleAccountCreator')
    thelogger.setLevel(logging.DEBUG)
    if not thelogger.handlers:
        handler = logging.handlers.SysLogHandler(address=(configs['logserveraddress'], 514))
        thelogger.addHandler(handler)

    return configs, thelogger

def get_engine(configs):
    """Creates and returns the SQLAlchemy engine."""
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    return create_engine(connection_url)

def export_google_users(thelogger):
    """Uses subprocess to dump current Google Student users to a CSV."""
    thelogger.info("Exporting current Google users via GAM...")
    print("Fetching current Google accounts (this may take a moment)...")
    
    gam_path = "gam" 
    command = f"{gam_path} print users query \"orgUnitPath='/Students'\" primaryEmail"
    
    with open('google_students.csv', 'w') as f:
        subprocess.run(command, shell=True, stdout=f, text=True)
    
    print("Google user export complete.")

def get_all_used_passwords(engine):
    """Pulls every existing password from AERIES to ensure global uniqueness."""
    query = "SELECT NID FROM STU WHERE NID != '' AND NID IS NOT NULL AND TG='' AND DEL=0"
    df_passwords = pd.read_sql_query(query, engine)
    return set(df_passwords['NID'].tolist())

def get_all_aeries_students(engine):
    """Pulls ALL active students (Grades 9-12+) from AERIES with dynamic OUs."""
    # We use nested CASE statements here to build the OU string dynamically 
    # based on both the School Code (SC) and the Grade Level (GR).
    query = r"""
    SELECT id, fn, ln, NID, STU.SC, STU.GR,
    CASE STU.SC
        WHEN 30 THEN '\Students\Transition'
        ELSE '\Students\' + 
            CASE STU.SC
                WHEN 1 THEN 'LLHS'
                WHEN 2 THEN 'AHS'
                WHEN 3 THEN 'MHS'
                WHEN 4 THEN 'CHS'
                WHEN 6 THEN 'CIS'
                WHEN 7 THEN 'CENR'
                ELSE 'Un Mapped School ABBR'
            END + '\' +
            CASE STU.GR
                WHEN 9 THEN 'Freshman'
                WHEN 10 THEN 'Sophomore'
                WHEN 11 THEN 'Junior'
                WHEN 12 THEN 'Senior'
                ELSE ''
            END
    END AS ou
    FROM stu
    WHERE STU.DEL = 0 AND STU.TG = '' AND STU.GR >= 9
    """
    return pd.read_sql_query(query, engine)

def update_aeries_password(engine, student_id, new_password, thelogger):
    """Writes a single new password back to AERIES."""
    update_query = text("UPDATE STU SET NID = :password WHERE ID = :student_id")
    try:
        with engine.begin() as conn:
            conn.execute(update_query, {"password": new_password, "student_id": student_id})
    except Exception as e:
        thelogger.error(f"Failed to update AERIES for {student_id}: {e}")
        print(f"CRITICAL ERROR updating AERIES for {student_id}: {e}")

def main():
    start_time = timer()
    configs, thelogger = setup_environment()
    engine = get_engine(configs)
    google_domain = configs.get('GoogleDomain', 'auhsdschools.org') 
    
    thelogger.info("--- Starting 2026 Google Account Reconciliation & Creation (All Grades) ---")
    
    # 1. Export current Google users to CSV
    export_google_users(thelogger)
    
    # 2. Load Google Users from the GAM CSV
    try:
        google_df = pd.read_csv('google_students.csv')
        existing_google_emails = set(google_df['primaryEmail'].str.lower())
    except FileNotFoundError:
        print("CRITICAL: google_students.csv not found. Aborting.")
        thelogger.error("google_students.csv not found. Aborting run.")
        return

    # 3. Load ALL Students from AERIES
    aeries_df = get_all_aeries_students(engine) 
    
    # Create ExpectedEmail column
    aeries_df['ExpectedEmail'] = aeries_df['id'].astype(str) + f"@{google_domain}"
    aeries_df['ExpectedEmail'] = aeries_df['ExpectedEmail'].str.lower()

    # 4. Find the missing students
    missing_students_df = aeries_df[~aeries_df['ExpectedEmail'].isin(existing_google_emails)]
    
    if missing_students_df.empty:
        print("Audit Complete: All students are already in Google Workspace.")
        thelogger.info("No missing students found. Exiting.")
        return
        
    print(f"Found {len(missing_students_df)} students missing from Google. Processing...")
    thelogger.info(f"Processing {len(missing_students_df)} missing students.")

    # 5. Seed used passwords for global uniqueness
    used_passwords = get_all_used_passwords(engine)
    success_count = 0

    # 6. Process each missing student
    for row in missing_students_df.itertuples():
        email = row.ExpectedEmail
        fn = str(row.fn).strip()
        ln = str(row.ln).strip()
        ou = str(row.ou).strip()
        password = str(row.NID).strip()
        
        # Generate and save a password if they don't have one in AERIES
        if pd.isna(row.NID) or password == '' or password == 'nan':
            password = create_password()
            while password in used_passwords:
                password = create_password()
            
            used_passwords.add(password)
            
            # Save the new password to AERIES immediately
            update_aeries_password(engine, row.id, password, thelogger)
            print(f"Generated new password for {row.id} and saved to AERIES.")

        # Build GAM command
        gam_args = [
            "create", "user", email,
            "firstname", fn,
            "lastname", ln,
            "password", password,
            "org", ou
        ]

        # Execute GAM
        try:
            print(f"Creating Google Account: {email} in {ou}")
            CallGAMCommand(gam_args)
            thelogger.info(f"SUCCESS: GAM account created for {email}")
            success_count += 1
        except Exception as e:
            thelogger.error(f"FAILED to create GAM account for {email}: {e}")
            print(f"ERROR creating {email}: {e}")

    end_time = timer()
    elapsed = round(end_time - start_time, 2)
    thelogger.info(f"--- Finished. Created {success_count} accounts in {elapsed} seconds. ---")
    print(f"\nDone! Successfully reconciled and created {success_count} accounts in {elapsed} seconds.")

if __name__ == '__main__':
    main()