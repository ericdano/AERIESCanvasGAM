import json
import urllib.parse
import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path
from canvasapi import Canvas

# --- Load Configs ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome, 'r') as f:
    configs = json.load(f)

# --- Database Setup ---
server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'
db_name = configs.get('LocalAUHSD') # Using the DB from your app.py
uid = configs.get('LocalAERIES_Username')
pwd = configs.get('LocalAERIES_Password')
odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# --- Canvas Setup ---
CANVAS_URL = "https://acalanes.instructure.com"
CANVAS_TOKEN = configs.get('CanvasAPIKey') # Assuming your token is in the JSON
canvas = Canvas(CANVAS_URL, CANVAS_TOKEN)

print("Connecting to database...")
with engine.begin() as conn:
    # 1. Safely add the new columns if they don't exist
    try:
        conn.execute(text("ALTER TABLE student_grades ADD sis_user_id VARCHAR(100);"))
        print("✅ Added sis_user_id column.")
    except Exception:
        print("ℹ️ sis_user_id column already exists.")
        
    try:
        conn.execute(text("ALTER TABLE student_grades ADD email VARCHAR(255);"))
        print("✅ Added email column.")
    except Exception:
        print("ℹ️ email column already exists.")

    # 2. Get unique Canvas student IDs that need updating
    print("Fetching students missing SIS IDs...")
    df_students = pd.read_sql("SELECT DISTINCT student_id FROM student_grades WHERE sis_user_id IS NULL", con=conn)
    print(f"Found {len(df_students)} unique students to update.")

# 3. Look up and update each student
    for index, row in df_students.iterrows():
        # THE FIX: Cast the numpy.int64 to a standard Python int
        c_id = int(row['student_id']) 
        
        try:
            # Query Canvas for the user profile
            user = canvas.get_user(c_id)
            sis = getattr(user, 'sis_user_id', None)
            email = getattr(user, 'email', getattr(user, 'login_id', None))
            
            # Update the SQL table where the Canvas ID matches
            conn.execute(text("""
                UPDATE student_grades 
                SET sis_user_id = :sis, email = :email 
                WHERE student_id = :cid
            """), {"sis": sis, "email": email, "cid": c_id})
            
            print(f"Updated Canvas ID {c_id} -> SIS: {sis} | Email: {email}")
        except Exception as e:
            print(f"⚠️ Failed to look up Canvas ID {c_id}: {e}")

print("🎉 Database fix complete!")