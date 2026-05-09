import os
import json
import urllib.parse
import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path
from canvasapi import Canvas
from datetime import datetime
import time

print("🚀 Starting Delta Gradebook Sync...")

# --- Load Configuration ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
try:
    with open(confighome, 'r') as f:
        configs = json.load(f)
except Exception as e:
    print(f"❌ Could not load config file: {e}")
    exit(1)

CANVAS_URL = "https://acalanes.instructure.com"
CANVAS_TOKEN = configs.get('CanvasAPIKey')
ACCOUNT_ID = 1
TARGET_TERM_IDS = configs.get('TargetTermIDs', [])

# --- Database Setup ---
server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'
db_name = configs.get('LocalAUHSD')
uid = configs.get('LocalAERIES_Username')
pwd = configs.get('LocalAERIES_Password')

odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)

# --- Helper Function: Clean Canvas Dates ---
def clean_canvas_date(date_string):
    if not date_string or pd.isna(date_string) or str(date_string).lower() in ['none', 'nan', 'nat']:
        return None
    try:
        dt = pd.to_datetime(date_string, utc=True)
        if dt.year < 1753 or dt.year > 9999:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return None

# --- Initialize Relational Tables ---
try:
    with engine.begin() as conn:
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='canvas_active_courses' and xtype='U')
            CREATE TABLE canvas_active_courses (course_id INT PRIMARY KEY, course_name VARCHAR(255))
        """))
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='canvas_assignments' and xtype='U')
            CREATE TABLE canvas_assignments (assignment_id INT PRIMARY KEY, course_id INT, title VARCHAR(255), points_possible FLOAT, due_at DATETIME)
        """))
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='canvas_scores' and xtype='U')
            CREATE TABLE canvas_scores (
                submission_id INT PRIMARY KEY, 
                assignment_id INT, 
                student_id INT, 
                score FLOAT, 
                grade VARCHAR(50), 
                workflow_state VARCHAR(50), 
                submitted_at DATETIME
            )
        """))
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='canvas_students' and xtype='U')
            CREATE TABLE canvas_students (
                student_id INT PRIMARY KEY, student_name VARCHAR(255), email VARCHAR(255), sis_user_id VARCHAR(100)
            )
        """))
        # NEW TABLE: To track our sync history for Delta pulls
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='canvas_sync_logs' and xtype='U')
            CREATE TABLE canvas_sync_logs (
                sync_id INT IDENTITY(1,1) PRIMARY KEY, sync_start DATETIME, status VARCHAR(50)
            )
        """))
except Exception as e:
    print(f"❌ Database Initialization Error: {e}")
    exit(1)

# --- Check Last Sync Time for Delta API Fetch ---
current_sync_start = datetime.utcnow()
last_sync_iso = None

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(sync_start) FROM canvas_sync_logs WHERE status = 'SUCCESS'")).fetchone()
        if result and result[0]:
            # Format to ISO 8601 for the Canvas API (e.g., 2025-05-08T12:00:00Z)
            last_sync_iso = result[0].strftime('%Y-%m-%dT%H:%M:%SZ')
            print(f"⚡ DELTA MODE ACTIVATED: Only fetching grades modified since {last_sync_iso}")
        else:
            print("📥 FULL SYNC MODE ACTIVATED: No previous log found. Downloading entire historical gradebook. This will take a while!")
except Exception as e:
    print(f"⚠️ Could not read sync logs: {e}")

# --- Connect to Canvas ---
try:
    canvas = Canvas(CANVAS_URL, CANVAS_TOKEN)
    account = canvas.get_account(ACCOUNT_ID)
except Exception as e:
    print(f"❌ Canvas Connection Error: {e}")
    exit(1)

courses = account.get_courses(enrollment_term_id=TARGET_TERM_IDS, state=['available'])

total_assignments_processed = 0
total_scores_processed = 0
total_students_processed = 0

for course in courses:
    try:
        print(f"\n📚 Course: {course.name} (ID: {course.id})")
        
        # 1. Fetch Students & Assignments
        users = course.get_users(enrollment_type=['student'], include=['email'])
        student_data = [{"student_id": u.id, "student_name": getattr(u, 'name', '')[:255], "email": getattr(u, 'email', getattr(u, 'login_id', None)), "sis_user_id": getattr(u, 'sis_user_id', None)} for u in users]

        assignments = course.get_assignments()
        assign_data = [{"assignment_id": a.id, "course_id": course.id, "title": a.name[:250], "points_possible": getattr(a, 'points_possible', None), "due_at": clean_canvas_date(getattr(a, 'due_at', None))} for a in assignments]
        
        # 2. DELTA OPTIMIZED SUBMISSION FETCH
        if last_sync_iso:
            # Only ask Canvas for things that were specifically graded OR submitted recently
            subs_graded = course.get_multiple_submissions(student_ids=['all'], graded_since=last_sync_iso)
            subs_submitted = course.get_multiple_submissions(student_ids=['all'], submitted_since=last_sync_iso)
            
            # Combine them into a dictionary to automatically remove duplicates
            unique_subs = {}
            for sub in subs_graded: unique_subs[sub.id] = sub
            for sub in subs_submitted: unique_subs[sub.id] = sub
            
            submissions_to_process = list(unique_subs.values())
        else:
            # If no last_sync date exists, download everything
            submissions_to_process = course.get_multiple_submissions(student_ids=['all'])

        sub_data = []
        for sub in submissions_to_process:
            if getattr(sub, 'workflow_state', 'unsubmitted') != 'deleted':
                sub_data.append({
                    "submission_id": sub.id, "assignment_id": sub.assignment_id, "student_id": sub.user_id,
                    "score": getattr(sub, 'score', None), "grade": str(getattr(sub, 'grade', ''))[:50] if getattr(sub, 'grade', None) else None,
                    "workflow_state": getattr(sub, 'workflow_state', None), "submitted_at": clean_canvas_date(getattr(sub, 'submitted_at', None))
                })

        # 3. WRITE TO DB USING DELTA "UPSERTS"
        with engine.begin() as conn:
            # --- Students Directory Upsert ---
            if student_data:
                df_students = pd.DataFrame(student_data).drop_duplicates(subset=['student_id'])
                df_students.to_sql('stg_canvas_students', con=engine, if_exists='replace', index=False)
                conn.execute(text("""
                    MERGE canvas_students AS target USING stg_canvas_students AS source ON target.student_id = source.student_id
                    WHEN MATCHED THEN UPDATE SET student_name = source.student_name, email = source.email, sis_user_id = source.sis_user_id
                    WHEN NOT MATCHED THEN INSERT (student_id, student_name, email, sis_user_id) VALUES (source.student_id, source.student_name, source.email, source.sis_user_id);
                """))
                total_students_processed += len(df_students)

            # --- Courses & Assignments Upsert ---
            pd.DataFrame([{"course_id": course.id, "course_name": course.name[:250]}]).to_sql('stg_canvas_courses', con=engine, if_exists='replace', index=False)
            conn.execute(text("""
                MERGE canvas_active_courses AS target USING stg_canvas_courses AS source ON target.course_id = source.course_id
                WHEN MATCHED THEN UPDATE SET course_name = source.course_name
                WHEN NOT MATCHED THEN INSERT (course_id, course_name) VALUES (source.course_id, source.course_name);
            """))
            
            if assign_data:
                pd.DataFrame(assign_data).to_sql('stg_canvas_assignments', con=engine, if_exists='replace', index=False)
                conn.execute(text("""
                    MERGE canvas_assignments AS target USING stg_canvas_assignments AS source ON target.assignment_id = source.assignment_id
                    WHEN MATCHED THEN UPDATE SET title = source.title, points_possible = source.points_possible, due_at = source.due_at, course_id = source.course_id
                    WHEN NOT MATCHED THEN INSERT (assignment_id, course_id, title, points_possible, due_at) VALUES (source.assignment_id, source.course_id, source.title, source.points_possible, source.due_at);
                """))
                total_assignments_processed += len(assign_data)
            
            # --- Scores Upsert ---
            if sub_data:
                pd.DataFrame(sub_data).to_sql('stg_canvas_scores', con=engine, if_exists='replace', index=False)
                conn.execute(text("""
                    MERGE canvas_scores AS target USING stg_canvas_scores AS source ON target.submission_id = source.submission_id
                    WHEN MATCHED AND (ISNULL(target.score, -999) <> ISNULL(source.score, -999) OR ISNULL(target.workflow_state, '') <> ISNULL(source.workflow_state, '') OR ISNULL(target.grade, '') <> ISNULL(source.grade, '')) 
                    THEN UPDATE SET assignment_id = source.assignment_id, student_id = source.student_id, score = source.score, grade = source.grade, workflow_state = source.workflow_state, submitted_at = source.submitted_at
                    WHEN NOT MATCHED THEN INSERT (submission_id, assignment_id, student_id, score, grade, workflow_state, submitted_at) VALUES (source.submission_id, source.assignment_id, source.student_id, source.score, source.grade, source.workflow_state, source.submitted_at);
                """))
                total_scores_processed += len(sub_data)

        print(f"   ✅ Checked {len(sub_data)} modified scores.")
        
    except Exception as e:
        print(f"   ⚠️ Error processing course {course.id}: {e}")

# --- Mark Sync as Successful ---
try:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO canvas_sync_logs (sync_start, status) VALUES (:start, 'SUCCESS')"), 
                     {"start": current_sync_start.strftime('%Y-%m-%d %H:%M:%S')})
except Exception as e:
    print(f"⚠️ Could not write success log: {e}")

print(f"\n🎉 Sync Complete! Updated {total_students_processed} students, {total_assignments_processed} assignments, and {total_scores_processed} delta scores.")