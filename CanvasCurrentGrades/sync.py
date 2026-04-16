
import os
import time
import json
import urllib.parse
import schedule
import pandas as pd
import concurrent.futures
from datetime import datetime
from canvasapi import Canvas
from sqlalchemy import create_engine
from pathlib import Path

# --- Helper to format Canvas ISO dates ---
def format_canvas_date(date_str):
    if not date_str:
        return "Never"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%b %d, %Y")
    except Exception:
        return str(date_str)

# --- Load Configuration ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
try:
    with open(confighome, 'r') as f:
        configs = json.load(f)
    API_URL = configs.get('CanvasAPIURL')
    API_KEY = configs.get('CanvasAPIKey')
    ACCOUNT_ID = configs.get('CanvasAccountID', 1) 
    TARGET_TERM_IDS = configs.get('TargetTermIDs')
    
    server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'
    db_name = configs.get('CanvasGradesDB')
    uid = configs.get('LocalAERIES_Username')
    pwd = configs.get('LocalAERIES_Password')
except Exception as e:
    print(f"Error loading config: {e}")
    exit(1)

# --- Database Connection ---
odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)
db_url = f"mssql+pyodbc:///?odbc_connect={params}"
engine = create_engine(db_url)

# --- Worker Function for Multithreading ---
def process_single_course(course, term_id, sync_timestamp):
    course_data = []
    try:
        teacher_names = [t.get('display_name', 'Unknown') for t in getattr(course, 'teachers', [])]
        instructor_string = ", ".join(teacher_names) if teacher_names else "No Instructor"
        
        users = list(course.get_users(enrollment_type=['student'], include=['enrollments']))
        if not users:
            return course_data
            
        user_ids = [u.id for u in users]
        student_stats = {uid: {'missing': 0, 'zeros': 0, 'latest_sub': None} for uid in user_ids}
        
        # Chunk logic inside the thread
        chunk_size = 50
        for i in range(0, len(user_ids), chunk_size):
            chunk = user_ids[i:i + chunk_size]
            chunk_subs = course.get_multiple_submissions(student_ids=chunk)
            
            for sub in chunk_subs:
                uid = getattr(sub, 'user_id', None)
                if not uid or uid not in student_stats:
                    continue
                    
                if getattr(sub, 'missing', False):
                    student_stats[uid]['missing'] += 1
                
                if getattr(sub, 'score', None) == 0:
                    student_stats[uid]['zeros'] += 1
                    
                sub_at = getattr(sub, 'submitted_at', None)
                if sub_at:
                    current_latest = student_stats[uid]['latest_sub']
                    if not current_latest or sub_at > current_latest:
                        student_stats[uid]['latest_sub'] = sub_at

        # Map back to student records
        for user in users:
            if hasattr(user, 'enrollments'):
                for enrollment in user.enrollments:
                    grades = enrollment.get('grades', {})
                    last_access_raw = enrollment.get('last_activity_at', None)
                    stats = student_stats.get(user.id, {})
                    
                    course_data.append({
                        'sync_timestamp': sync_timestamp,
                        'term_id': term_id,
                        'course_id': course.id,
                        'course_name': course.name,
                        'instructors': instructor_string,
                        'student_name': user.name,
                        'current_score': grades.get('current_score'),
                        'current_grade': grades.get('current_grade'),
                        'last_access': format_canvas_date(last_access_raw),
                        'missing_assignments': stats.get('missing', 0),
                        'zeros': stats.get('zeros', 0),
                        'latest_submission': format_canvas_date(stats.get('latest_sub'))
                    })
        print(f"[{datetime.now()}]   ✅ Finished Course {course.id}: {getattr(course, 'name', 'Unknown')}")
    except Exception as e:
        print(f"[{datetime.now()}]   ❌ Skipped Course {course.id}: {e}")
        
    return course_data

# --- Main Sync Logic ---
def run_sync():
    print(f"[{datetime.now()}] 🚀 Starting scheduled Canvas sync with MULTITHREADING...")
    canvas = Canvas(API_URL, API_KEY)
    sync_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        account = canvas.get_account(ACCOUNT_ID)
        all_grades_data = []

        for term_id in TARGET_TERM_IDS:
            print(f"[{datetime.now()}] Fetching course list for Term ID: {term_id}...")
            courses = list(account.get_courses(enrollment_term_id=term_id, state=['available'], include=['teachers']))
            print(f"[{datetime.now()}] Found {len(courses)} courses. Dispatching threads...")
            
            # Spin up 15 parallel workers to process courses simultaneously
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                # Map the process_single_course function to our list of courses
                futures = [executor.submit(process_single_course, course, term_id, sync_timestamp) for course in courses]
                
                # Gather the results as each thread finishes
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        all_grades_data.extend(result)
                    
        if all_grades_data:
            df = pd.DataFrame(all_grades_data)
            df.to_sql(name='student_grades', con=engine, if_exists='append', index=False)
            print(f"[{datetime.now()}] 🎉 Successfully synced {len(df)} records!")
        else:
            print(f"[{datetime.now()}] ⚠️ No data found for the provided Term IDs.")

    except Exception as e:
        print(f"[{datetime.now()}] ❌ Canvas API Error: {e}")

# --- Scheduler Setup ---
schedule.every().day.at("06:30").do(run_sync)
print(f"[{datetime.now()}] 🕰️ Background Scheduler started.")

run_sync()

print(f"[{datetime.now()}] ⏳ Initial sync complete. Waiting for the next scheduled run at 06:30 AM...")

while True:
    schedule.run_pending()
    time.sleep(60)