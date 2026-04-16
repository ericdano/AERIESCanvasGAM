import os
import time
import json
import urllib.parse
import schedule
import pandas as pd
import concurrent.futures
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

# --- Worker Function for Delta Multithreading ---
def process_single_course(course, term_id, new_sync_timestamp, cutoff_utc):
    course_data = []
    try:
        teacher_names = [t.get('display_name', 'Unknown') for t in getattr(course, 'teachers', [])]
        instructor_string = ", ".join(teacher_names) if teacher_names else "No Instructor"
        
        users = list(course.get_users(enrollment_type=['student'], include=['enrollments']))
        if not users:
            return course_data
            
        # 1. DELTA FILTER: Only flag students who have had activity since the cutoff
        delta_users = []
        for u in users:
            changed = False
            for e in getattr(u, 'enrollments', []):
                updated_at_str = e.get('updated_at')
                if updated_at_str:
                    try:
                        # Canvas uses UTC for all timestamps
                        updated_dt = datetime.strptime(updated_at_str, "%Y-%m-%dT%H:%M:%SZ")
                        if updated_dt > cutoff_utc:
                            changed = True
                            break
                    except Exception:
                        changed = True
                else:
                    changed = True # Safety net: if we can't tell, assume they need updating
                    
            if changed:
                delta_users.append(u)
                
        if not delta_users:
            # Huge optimization: No students changed, skip the heavy API calls completely!
            print(f"[{datetime.now()}]   ⏩ No changes in Course {course.id}. Skipping heavy fetch.")
            return course_data

        print(f"[{datetime.now()}]   ⏳ Course {course.id}: Fetching {len(delta_users)} updated students...")

        user_ids = [u.id for u in delta_users]
        student_stats = {uid: {'missing': 0, 'zeros': 0, 'latest_sub': None} for uid in user_ids}
        
        # 2. HEAVY FETCH: Only fetch submissions for the changed students (Chunked by 50 to prevent API crashes)
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

        # 3. MAP BACK
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
                        'student_name': user.name,
                        'current_score': grades.get('current_score'),
                        'current_grade': grades.get('current_grade'),
                        'last_access': format_canvas_date(last_access_raw),
                        'missing_assignments': stats.get('missing', 0),
                        'zeros': stats.get('zeros', 0),
                        'latest_submission': format_canvas_date(stats.get('latest_sub'))
                    })
        print(f"[{datetime.now()}]   ✅ Finished updates for Course {course.id}")
    except Exception as e:
        print(f"[{datetime.now()}]   ❌ Skipped Course {course.id}: {e}")
        
    return course_data

def run_sync():
    print(f"[{datetime.now()}] 🚀 Starting scheduled Sync...")
    canvas = Canvas(API_URL, API_KEY)
    
    new_sync_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # === PHASE 1: CLONE THE DATABASE ===
        print(f"[{datetime.now()}] 🗄️ Phase 1: Checking for previous database snapshots...")
        try:
            query_latest = "SELECT MAX(sync_timestamp) FROM student_grades"
            last_sync_df = pd.read_sql(query_latest, con=engine)
            last_sync = last_sync_df.iloc[0, 0] if not last_sync_df.empty else None
        except Exception:
            last_sync = None
            
        if last_sync:
            print(f"[{datetime.now()}] 🗄️ Cloning snapshot from {last_sync} to {new_sync_timestamp}...")
            # Normal 48-hour lookback for Deltas
            cutoff_utc = datetime.utcnow() - timedelta(hours=48)
            
            clone_sql = text("""
                INSERT INTO student_grades (sync_timestamp, term_id, course_id, course_name, instructors, student_name, current_score, current_grade, last_access, missing_assignments, zeros, latest_submission)
                SELECT :new_sync, term_id, course_id, course_name, instructors, student_name, current_score, current_grade, last_access, missing_assignments, zeros, latest_submission
                FROM student_grades
                WHERE sync_timestamp = :last_sync
            """)
            with engine.begin() as conn:
                conn.execute(clone_sql, {"new_sync": new_sync_timestamp, "last_sync": last_sync})
            print(f"[{datetime.now()}] ✅ Clone complete!")
        else:
            print(f"[{datetime.now()}] ⚠️ No previous data found. Performing a FULL INITIAL BASELINE SYNC.")
            # Set cutoff to 10 years ago so it grabs literally every student's history
            cutoff_utc = datetime.utcnow() - timedelta(days=3650)

        # === PHASE 2: DELTA FETCH ===
        print(f"[{datetime.now()}] 🌐 Phase 2: Fetching data from Canvas...")
        account = canvas.get_account(ACCOUNT_ID)
        all_delta_data = []

        for term_id in TARGET_TERM_IDS:
            print(f"[{datetime.now()}] Fetching course list for Term ID: {term_id}...")
            courses = list(account.get_courses(enrollment_term_id=term_id, state=['available'], include=['teachers']))
            print(f"[{datetime.now()}] Found {len(courses)} courses. Dispatching threads...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                futures = [executor.submit(process_single_course, course, term_id, new_sync_timestamp, cutoff_utc) for course in courses]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        all_delta_data.extend(result)

        # === PHASE 3: THE MERGE ===
        print(f"[{datetime.now()}] 🔄 Phase 3: Merging data...")
        if all_delta_data:
            delta_df = pd.DataFrame(all_delta_data)
            
            if last_sync:
                print(f"[{datetime.now()}] Removing stale cloned rows for the {len(delta_df)} updated records...")
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

            print(f"[{datetime.now()}] Pushing {len(delta_df)} new updates to the database...")
            delta_df.to_sql(name='student_grades', con=engine, if_exists='append', index=False)
            print(f"[{datetime.now()}] 🎉 Sync complete!")
        else:
            print(f"[{datetime.now()}] 🤷 No grade changes detected.")

    except Exception as e:
        print(f"[{datetime.now()}] ❌ Fatal Sync Error: {e}")

# --- Scheduler Setup ---
schedule.every().day.at("06:30").do(run_sync)
print(f"[{datetime.now()}] 🕰️ Background Scheduler started.")

# Run immediately upon container start
run_sync()

print(f"[{datetime.now()}] ⏳ Initial sync routine complete. Waiting for the next scheduled run at 06:30 AM...")

while True:
    schedule.run_pending()
    time.sleep(60)