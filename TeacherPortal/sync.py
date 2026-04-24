import os
import time
import json
import urllib.parse
import schedule
import smtplib
import pandas as pd
import concurrent.futures
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from canvasapi import Canvas
from sqlalchemy import create_engine, text
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
    db_name = configs.get('CanvasDatabase')
    uid = configs.get('LocalAERIES_Username')
    pwd = configs.get('LocalAERIES_Password')
    
    # Updated Email Configs using your JSON keys
    SMTP_SERVER = configs.get('SMTPServerAddress', '10.99.0.202')
    SMTP_FROM = configs.get('SMTPAddressFrom', 'donotreply@auhsdschools.org')
    ALERT_EMAIL = configs.get('SendInfoEmailAddr', 'edannewitz@auhsdschools.org')
except Exception as e:
    print(f"Error loading config: {e}")
    exit(1)

# --- Database Connection ---
odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)
db_url = f"mssql+pyodbc:///?odbc_connect={params}"
engine = create_engine(db_url)

# --- Email Helper Function (Unsecured Port 25 Relay) ---
def send_completion_email(sync_time, mode):
    if not SMTP_SERVER or not ALERT_EMAIL:
        return
    try:
        msg = MIMEText(f"The Canvas Grade Extractor has successfully completed a {mode} sync at {sync_time} PDT.")
        msg['Subject'] = f"✅ Canvas Data Sync Complete ({mode})"
        msg['From'] = SMTP_FROM
        msg['To'] = ALERT_EMAIL

        # Connects to your local unsecured SMTP server on port 25
        with smtplib.SMTP(SMTP_SERVER, 25) as server: 
            server.send_message(msg)
            
        print(f"[{datetime.now()}] 📧 Success email sent to {ALERT_EMAIL}")
    except Exception as e:
        print(f"[{datetime.now()}] ⚠️ Could not send email: {e}")

# --- Worker Function for Delta Multithreading ---
def process_single_course(course, term_id, new_sync_timestamp, cutoff_utc):
    print(f"[{datetime.now()}]   🧵 Thread started for Course {course.id}. Fetching roster...")
    course_data = []
    try:
        teacher_names = [t.get('display_name', 'Unknown') for t in getattr(course, 'teachers', [])]
        instructor_string = ", ".join(teacher_names) if teacher_names else "No Instructor"
        
        users = list(course.get_users(enrollment_type=['student'], include=['enrollments']))
        if not users:
            return course_data
            
        delta_users = []
        for u in users:
            changed = False
            for e in getattr(u, 'enrollments', []):
                updated_at_str = e.get('updated_at')
                if updated_at_str:
                    try:
                        updated_dt = datetime.strptime(updated_at_str, "%Y-%m-%dT%H:%M:%SZ")
                        if updated_dt > cutoff_utc:
                            changed = True
                            break
                    except Exception:
                        changed = True
                else:
                    changed = True 
                    
            if changed:
                delta_users.append(u)
                
        if not delta_users:
            print(f"[{datetime.now()}]   ⏩ No changes in Course {course.id}. Skipping heavy fetch.")
            return course_data

        user_ids = [u.id for u in delta_users]
        student_stats = {uid: {'missing': 0, 'zeros': 0, 'latest_sub': None} for uid in user_ids}
        
        chunk_size = 50
        for i in range(0, len(user_ids), chunk_size):
            chunk = user_ids[i:i + chunk_size]
            chunk_subs = course.get_multiple_submissions(student_ids=chunk, include=['assignment'])
            
            for sub in chunk_subs:
                uid = getattr(sub, 'user_id', None)
                if not uid or uid not in student_stats:
                    continue
                    
                if getattr(sub, 'excused', False) or getattr(sub, 'workflow_state', '') == 'deleted':
                    continue
                    
                assignment = getattr(sub, 'assignment', {})
                if assignment.get('points_possible', 1) == 0:
                    continue

                is_missing = getattr(sub, 'missing', False)
                score = getattr(sub, 'score', None)

                if is_missing:
                    student_stats[uid]['missing'] += 1
                elif score == 0 or score == 0.0:
                    student_stats[uid]['zeros'] += 1
                    
                sub_at = getattr(sub, 'submitted_at', None)
                if sub_at:
                    current_latest = student_stats[uid]['latest_sub']
                    if not current_latest or sub_at > current_latest:
                        student_stats[uid]['latest_sub'] = sub_at

        for user in delta_users:
            if hasattr(user, 'enrollments'):
                for enrollment in user.enrollments:
                    grades = enrollment.get('grades', {})
                    last_access_raw = enrollment.get('last_activity_at', None)
                    stats = student_stats.get(user.id, {})
                    
                    course_data.append({
                        'sync_timestamp': new_sync_timestamp,
                        'term_id': term_id,
                        'course_id': course.id,
                        'course_name': course.name,
                        'instructors': instructor_string,
                        'student_id': user.id,   
                        'student_name': user.name,
                        'current_score': grades.get('current_score'),
                        'current_grade': grades.get('current_grade'),
                        'last_access': format_canvas_date(last_access_raw),
                        'missing_assignments': stats.get('missing', 0),
                        'zeros': stats.get('zeros', 0),
                        'latest_submission': format_canvas_date(stats.get('latest_sub'))
                    })
    except Exception as e:
        print(f"[{datetime.now()}]   ❌ Skipped Course {course.id}: {e}")
        
    return course_data

def run_sync():
    print(f"[{datetime.now()}] 🚀 Starting scheduled Sync...")
    canvas = Canvas(API_URL, API_KEY)
    new_sync_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_mode = "Delta"
    
    try:
        try:
            history_df = pd.read_sql("SELECT MAX(sync_timestamp) FROM sync_history WHERE status = 'COMPLETE'", con=engine)
            last_valid_sync = history_df.iloc[0, 0] if not history_df.empty else None
            
            if last_valid_sync:
                check_data = pd.read_sql(f"SELECT TOP 1 1 FROM student_grades WHERE sync_timestamp = '{last_valid_sync}'", con=engine)
                if check_data.empty:
                    last_valid_sync = None 
        except Exception:
            last_valid_sync = None

        completed_resume_courses = []

        if last_valid_sync:
            print(f"[{datetime.now()}] 🗄️ Last complete sync found at {last_valid_sync}. Cloning to {new_sync_timestamp}...")
            cutoff_utc = datetime.utcnow() - timedelta(hours=48)
            
            clone_sql = text("""
                INSERT INTO student_grades (sync_timestamp, term_id, course_id, course_name, instructors, student_id, student_name, current_score, current_grade, last_access, missing_assignments, zeros, latest_submission)
                SELECT :new_sync, term_id, course_id, course_name, instructors, student_id, student_name, current_score, current_grade, last_access, missing_assignments, zeros, latest_submission
                FROM student_grades
                WHERE sync_timestamp = :last_sync
            """)
            with engine.begin() as conn:
                conn.execute(clone_sql, {"new_sync": new_sync_timestamp, "last_sync": last_valid_sync})
            print(f"[{datetime.now()}] ✅ Clone complete!")
            
        else:
            sync_mode = "Initial Baseline"
            print(f"[{datetime.now()}] ⚠️ No valid history found. Operating in INITIAL BASELINE mode.")
            cutoff_utc = datetime.utcnow() - timedelta(days=3650)
            
            try:
                crashed_df = pd.read_sql("SELECT MAX(sync_timestamp) FROM student_grades", con=engine)
                crashed_ts = crashed_df.iloc[0, 0] if not crashed_df.empty else None
            except Exception:
                crashed_ts = None
                
            if crashed_ts:
                new_sync_timestamp = crashed_ts 
                df_completed = pd.read_sql(f"SELECT DISTINCT course_id FROM student_grades WHERE sync_timestamp = '{crashed_ts}'", con=engine)
                completed_resume_courses = df_completed['course_id'].tolist()
                print(f"[{datetime.now()}] ⏭️ Resuming crashed sync. Skipping {len(completed_resume_courses)} courses.")

        account = canvas.get_account(ACCOUNT_ID)

        for term_id in TARGET_TERM_IDS:
            print(f"[{datetime.now()}] 🌐 Fetching course list for Term ID: {term_id}...")
            courses = list(account.get_courses(
                enrollment_term_id=term_id, 
                state=['available'], 
                include=['teachers'], 
                per_page=100
            ))
            
            if completed_resume_courses:
                courses = [c for c in courses if c.id not in completed_resume_courses]
            print(f"[{datetime.now()}] 📚 Found {len(courses)} courses. Dispatching threads...")    
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                futures = [executor.submit(process_single_course, course, term_id, new_sync_timestamp, cutoff_utc) for course in courses]
                
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        delta_df = pd.DataFrame(result)
                        course_id_log = delta_df.iloc[0]['course_id']
                        
                        if last_valid_sync:
                            delete_sql = text("""
                                DELETE FROM student_grades 
                                WHERE sync_timestamp = :sync_ts 
                                AND course_id = :c_id 
                                AND student_name = :s_name
                            """)
                            delete_params = [
                                {"sync_ts": new_sync_timestamp, "c_id": row['course_id'], "s_name": row['student_name']}
                                for _, row in delta_df.iterrows()
                            ]
                            with engine.begin() as conn:
                                conn.execute(delete_sql, delete_params)
                                
                        delta_df.to_sql(name='student_grades', con=engine, if_exists='append', index=False)
                        print(f"[{datetime.now()}]   💾 Saved updates for Course {course_id_log}")

        # === PHASE 3: MARK AS COMPLETE & SEND EMAIL ===
        print(f"[{datetime.now()}] 🏁 Marking sync {new_sync_timestamp} as COMPLETE.")
        pd.DataFrame([{'sync_timestamp': new_sync_timestamp, 'status': 'COMPLETE'}]).to_sql('sync_history', con=engine, if_exists='append', index=False)
        
        # Trigger the newly added email alert
        send_completion_email(new_sync_timestamp, sync_mode)

    except Exception as e:
        print(f"[{datetime.now()}] ❌ Fatal Sync Error: {e}")

# --- Scheduler Setup ---
schedule.every().day.at("06:30").do(run_sync)
print(f"[{datetime.now()}] 🕰️ Background Scheduler started.")
run_sync()
print(f"[{datetime.now()}] ⏳ Initial sync routine complete. Waiting for the next scheduled run at 06:30 AM...")

while True:
    schedule.run_pending()
    
    # Send a "heartbeat" to Docker so Komodo knows the container isn't frozen
    Path('/tmp/heartbeat.txt').touch()
    
    time.sleep(60)