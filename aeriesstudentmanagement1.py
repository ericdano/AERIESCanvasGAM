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
    query = f"""
    SELECT NID FROM
      STU 
    WHERE DEL = 0 AND TG = '' AND NID != '' AND NID IS NOT NULL"""
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
                ELSE 'Unmapped'
            END + '\' +
            CASE STU.GR
                WHEN 9 THEN 'Freshman'
                WHEN 10 THEN 'Sophomore'
                WHEN 11 THEN 'Junior'
                WHEN 12 THEN 'Senior'
                ELSE 'Other'
            END
    END AS ou
    FROM stu
    WHERE STU.DEL = 0 AND STU.GR >= 9
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