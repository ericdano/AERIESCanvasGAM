import os
import time
import json
import schedule
import pandas as pd
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
except Exception as e:
    print(f"Error loading config: {e}")
    exit(1)

# --- Database Connection ---
db_url = os.getenv("DATABASE_URL", "mysql+pymysql://canvas_user:canvas_password@db:3306/canvas_data")

def run_sync():
    print(f"[{datetime.now()}] 🚀 Starting scheduled Canvas sync...")
    canvas = Canvas(API_URL, API_KEY)
    sync_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        account = canvas.get_account(ACCOUNT_ID)
        all_grades_data = []

        for term_id in TARGET_TERM_IDS:
            print(f"[{datetime.now()}] Fetching courses for Term ID: {term_id}...")
            courses = account.get_courses(enrollment_term_id=term_id, state=['available'], include=['teachers'])
            
            for course in courses:
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
                except Exception:
                    pass 
                    
        if all_grades_data:
            df = pd.DataFrame(all_grades_data)
            df.to_sql(name='student_grades', con=db_url, if_exists='append', index=False)
            print(f"[{datetime.now()}] ✅ Successfully synced {len(df)} records!")
        else:
            print(f"[{datetime.now()}] ⚠️ No data found for the provided Term IDs.")

    except Exception as e:
        print(f"[{datetime.now()}] ❌ Canvas API Error: {e}")

# --- Scheduler Setup ---
# Set the schedule to run every day at 6:30 AM
schedule.every().day.at("06:30").do(run_sync)

print(f"[{datetime.now()}] 🕰️ Background Scheduler started. Waiting for 06:30 AM...")

# Keep the script alive and checking the time
while True:
    schedule.run_pending()
    time.sleep(60) # Check the clock every 60 seconds