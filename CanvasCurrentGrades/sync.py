import urllib.parse
import os
import time
import json
import schedule
import smtplib
import pandas as pd
from email.message import EmailMessage
from datetime import datetime
from canvasapi import Canvas
from sqlalchemy import create_engine
from pathlib import Path

# --- Load Configuration ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
try:
    with open(confighome, 'r') as f:
        configs = json.load(f)
    API_URL = configs.get('CanvasAPIURL')
    API_KEY = configs.get('CanvasAPIKey')
    ACCOUNT_ID = configs.get('CanvasAccountID', 1) 
    TARGET_TERM_IDS = configs.get('TargetTermIDs')
    
    # Email Configs
    SMTP_SERVER = configs.get('SMTPServerAddress', 'host.docker.internal')
    EMAIL_FROM = 'donotreply@auhsdschools.org'
    EMAIL_TO = configs.get('SendInfoEmailAddr')
except Exception as e:
    print(f"Error loading config: {e}")
    exit(1)
# --- Database Connection ---
server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'
db_name = configs.get('CanvasGradesDB')
uid = configs.get('LocalAERIES_Username')
pwd = configs.get('LocalAERIES_Password')

if not db_name or not uid or not pwd:
    st.error("Missing Aeries MSSQL Database credentials in Acalanes.json")
    st.stop()

# Safely encode the connection string for SQLAlchemy
odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)

db_url = f"mssql+pyodbc:///?odbc_connect={params}"
engine = create_engine(db_url)

# --- Email Notification Function ---
def send_status_email(subject, body):
    if not EMAIL_TO:
        print("⚠️ No Admin_Email configured. Skipping email notification.")
        return
        
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        
        # Connects to port 25 with no authentication
        with smtplib.SMTP(SMTP_SERVER, 25) as s:
            s.send_message(msg)
        print("📧 Status email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send status email: {e}")

# --- Core Sync Logic ---
def run_sync():
    print(f"[{datetime.now()}] 🚀 Starting scheduled Canvas sync...")
    canvas = Canvas(API_URL, API_KEY)
    sync_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        account = canvas.get_account(ACCOUNT_ID)
        all_grades_data = []

        for term_id in TARGET_TERM_IDS:
            print(f"[{datetime.now()}] Fetching courses for Term ID: {term_id}...")
            
            # 1. Fetch Courses with Retry Logic
            courses = None
            for attempt in range(3):
                try:
                    courses = account.get_courses(enrollment_term_id=term_id, state=['available'], include=['teachers'])
                    break # Success, break out of retry loop
                except Exception as e:
                    print(f"⚠️ Error fetching courses (Attempt {attempt+1}/3): {e}")
                    time.sleep(10 * (attempt + 1)) # Exponential backoff (10s, 20s, 30s)
            
            if not courses:
                raise Exception(f"Failed to fetch courses for Term {term_id} after 3 attempts.")

            # 2. Process Users inside Courses
            for course in courses:
                for attempt in range(3):
                    try:
                        teacher_names = [t.get('display_name', 'Unknown') for t in getattr(course, 'teachers', [])]
                        instructor_string = ", ".join(teacher_names) if teacher_names else "No Instructor"
                        users = course.get_users(enrollment_type=['student'], include=['enrollments'])
                        
                        for user in users:
                            if hasattr(user, 'enrollments'):
                                for enrollment in user.enrollments:
                                    grades = enrollment.get('grades', {})
                                    all_grades_data.append({
                                        'sync_timestamp': sync_timestamp,
                                        'term_id': term_id,
                                        'course_id': course.id,
                                        'course_name': course.name,
                                        'instructors': instructor_string,
                                        'student_name': user.name,
                                        'current_score': grades.get('current_score'),
                                        'current_grade': grades.get('current_grade')
                                    })
                        break # Success, break out of retry loop for this course
                    except Exception as e:
                        time.sleep(5) # Small backoff for individual course hiccups
                    
        # 3. Push to Database
        if all_grades_data:
            df = pd.DataFrame(all_grades_data)
            df.to_sql(name='student_grades', con=db_url, if_exists='append', index=False)
            
            success_msg = f"Successfully synced {len(df)} records across {len(TARGET_TERM_IDS)} terms."
            print(f"[{datetime.now()}] ✅ {success_msg}")
            send_status_email(f"✅ Canvas Sync Success: {len(df)} records", f"The automated sync completed at {sync_timestamp}.\n\n{success_msg}")
        else:
            warn_msg = "No data found for the provided Term IDs."
            print(f"[{datetime.now()}] ⚠️ {warn_msg}")
            send_status_email("⚠️ Canvas Sync Warning: No Data", f"The automated sync ran at {sync_timestamp} but found no student grade data.")

    except Exception as e:
        error_msg = f"A critical error occurred during the sync process:\n\n{str(e)}"
        print(f"[{datetime.now()}] ❌ Canvas API Error: {e}")
        send_status_email("❌ Canvas Sync ERROR", error_msg)

# --- Scheduler Setup ---
schedule.every().day.at("06:30").do(run_sync)
print(f"[{datetime.now()}] 🕰️ Background Scheduler started. Waiting for 06:30 AM...")

while True:
    schedule.run_pending()
    time.sleep(60)