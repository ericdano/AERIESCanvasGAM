import random
import string
import pandas as pd
import os, sys, shlex, subprocess, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine, text
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
import multiprocessing
import platform
from gam import initializeLogging, CallGAMCommand
"""
Python 3.14 Script to generate Staff passwords for new Staff
"""


# --- 1. Define Character Sets ---
VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnprstvw"
# Letters that can be replaced by a symbol
REPLACEABLE_LETTERS = "asihle"
SYMBOL_MAP = {
    'a': '@',
    's': '$',
    'i': '!',
    'l': '!',
    'h': '#',
    'e': '&'
    }
# --- 4. Add words to this list to filter them out ---
OFFENSIVE_WORDS = [
    # General profanity
    "fuck", "shit", "damn", "hell", "piss", "crap", "bitch", "bastard",
    
    # Anatomical/Sexual terms
    "sex", "porn", "anal", "ass", "butt", "tit", "boob", "penis", "dick", 
    "vagina", "cunt", "clit", "balls", "nuts", "jizz", "shaft", "hardon",
    
    # Slurs and Hate Speech (Crucial for school environments)
    "fag", "gay", "homo", "nigger", "spic", "chink", "kike", "retard",
    
    # Common insults/Mean-spirited words
    "dumb", "stupid", "idiot", "fat", "ugly", "obese", "loser", "hate",
    "kill", "die", "slave", "nazi", "hitler","obese",
    "nigger", "nigga", "fag", "faggot", "kike", "spic", "chink", "cunt", 
    "retard", "tranny", "dyke", "nazi", "hitler", "negro",

    # --- Tier 2: Sexual & Anatomical Slang ---
    "fuck", "shit", "bitch", "whore", "slut", "porn", "anal", "vagina", 
    "penis", "dick", "cock", "tits", "boob", "clit", "jizz", "cum", 
    "boner", "balls", "nuts", "bastard", "twat", "wanker", "prick",

    # --- Tier 3: Modern Internet Slang & Evasion Terms ---
    "seggs", "unalive", "kys", "stfu", "pwned", "haxor", "n00b", "leets",

    # --- Tier 4: School-Specific Mean-Spirited Words ---
    "ugly", "fat", "obese", "stupid", "idiot", "dumb", "loser", "hate", 
    "kill", "die", "slave", "freak", "weirdo", "scum", "trash"
]
def create_password():
    """Generates a single, unique password based on the specified rules."""
    while True:
        # --- 1. Create a base word ---
        word = ""
        for i in range(3):
            word += random.choice(CONSONANTS)
            word += random.choice(VOWELS)

        is_offensive = any(bad_word in word for bad_word in OFFENSIVE_WORDS)
        has_replaceable = any(char in word for char in REPLACEABLE_LETTERS)

        # Everything from here down must stay inside the 'if' block
        if not is_offensive and has_replaceable:
            # --- 2. Substitute a special symbol ---
            replaceable_chars = [char for char in word if char in REPLACEABLE_LETTERS]
            char_to_replace = random.choice(replaceable_chars)
            symbol = SYMBOL_MAP[char_to_replace]

            # Replace the symbol
            word_with_symbol = word.replace(char_to_replace, symbol, 1)

            # Capitalize
            final_word = word_with_symbol.capitalize()

            # --- 3. Append digits ---
            three_digits = f"{random.randint(0, 999):03d}"

            # Return ends the while loop and the function
            return final_word + three_digits
def GetAERIESData(thelogger,configs):
    os.chdir(configs['PythonTempDirectory'])
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsernameE'] + ";PWD=" + configs['AERIESPasswordE'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    thelogger.info('CreateNewStudentsInGoogle2026->Connecting To AERIES to get ALL 9th Graders without Passwords')
       
    findquery = fr"""
    select id, sem, fn, ln, STU.SC,
    CASE STU.SC
        WHEN 1 THEN '\Students\LLHS\Freshman'
        WHEN 2 THEN '\Students\AHS\Freshman'
        WHEN 3 THEN '\Students\MHS\Freshman'
        WHEN 4 THEN '\Students\CHS\Freshman'
        WHEN 6 THEN '\Students\CIS\Freshman'
        WHEN 7 THEN '\Students\CENR\Freshman'
        WHEN 30 THEN '\Students\Transition'
        ELSE '\Students\Un Mapped School ABBR'
    END AS ou,
    nid, sem from stu
    where STU.DEL = 0 AND STU.TG = '' AND gr = 9 AND NID = ''
    """
    sql_query = pd.read_sql_query(findquery,engine)       
    return sql_query
def UpdateAERIESPasswords(thelogger, configs, df):
    """Writes the newly generated passwords back to the NID column in AERIES."""
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsernameE'] + ";PWD=" + configs['AERIESPasswordE'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    
    thelogger.info(f"Updating NID for {len(df)} students in AERIES.")
    
    # The parameterized SQL query
    update_query = text("UPDATE STU SET NID = :password WHERE ID = :student_id")
    
    # engine.begin() automatically commits the transaction if the loop finishes without crashing
    try:
        with engine.begin() as conn:
            for row in df.itertuples(index=True):
                # Only run the update if a new password exists
                if pd.notna(row.NewPassword) and str(row.NewPassword).strip() != '':
                    # Pass the exact variables to the parameter placeholders
                    conn.execute(update_query, {"password": row.NewPassword, "student_id": row.id})
                    
        thelogger.info("Successfully updated AERIES with new passwords.")
        print("Database Update Complete!")
        
    except Exception as e:
        thelogger.error(f"Failed to update AERIES: {e}")
        print(f"CRITICAL ERROR updating AERIES: {e}")
def main():
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    
    with open(confighome) as f:
        configs = json.load(f)
        
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'], 514))
    thelogger.addHandler(handler)
    
    # Fetch the dataframe
    studentstoprocess = GetAERIESData(thelogger, configs)
    
    # Create a set to track used passwords for uniqueness
    used_passwords = set()
    
    # Create a list to hold the newly generated passwords in order
    assigned_passwords = []

    for row in studentstoprocess.itertuples(index=True):
        # Handle both pandas NaN/Null and empty strings
        if pd.isna(row.nid) or str(row.nid).strip() == '':
            
            # Generate a password and check it against the used set
            new_password = create_password()
            while new_password in used_passwords:
                new_password = create_password()
                
            # Add to our tracking set and our column list
            used_passwords.add(new_password)
            assigned_passwords.append(new_password)
            
            print(f"ID: {row.id} | sem: {row.sem} | Name: {row.fn} {row.ln} | OU: {row.ou} | New Pass: {new_password}")
        else:
            # If a student somehow already has an NID, retain it or append a blank
            assigned_passwords.append(row.nid)

    # Assign the new list back to the DataFrame as a new column
    studentstoprocess['NewPassword'] = assigned_passwords
    
    # Log the completion
    thelogger.info(f"Successfully generated {len(used_passwords)} unique passwords.")
    
    # Next steps: You can now use studentstoprocess['NewPassword'] to update Aeries or GAM
    # Assign the new list back to the DataFrame as a new column
    studentstoprocess['NewPassword'] = assigned_passwords
    
    # Log the completion
    thelogger.info(f"Successfully generated {len(used_passwords)} unique passwords.")
    
    # Write back to AERIES
    UpdateAERIESPasswords(thelogger, configs, studentstoprocess)

if __name__ == '__main__':
    main()