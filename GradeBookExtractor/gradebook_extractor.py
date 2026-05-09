import os
import json
import urllib.parse
import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path
from canvasapi import Canvas
import time

print("🚀 Starting Full Gradebook Extraction...")

# --- Load Configuration ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome, 'r') as f:
    configs = json.load(f)

CANVAS_URL = "https://acalanes.instructure.com"
CANVAS_TOKEN = configs.get('CanvasToken')
ACCOUNT_ID = configs.get('CanvasAccountID', 1)
TARGET_TERM_IDS = configs.get('TargetTermIDs', [])

# --- Database Setup ---
server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'
db_name = configs.get('LocalAUHSD')
uid = configs.get('LocalAERIES_Username')
pwd = configs.get('LocalAERIES_Password')

odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)

# --- Initialize Relational Tables ---
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

# --- Connect to Canvas ---
canvas = Canvas(CANVAS_URL, CANVAS_TOKEN)
account = canvas.get_account(ACCOUNT_ID)

print("Fetching active courses for the current term(s)...")
courses = account.get_courses(enrollment_term_id=TARGET_TERM_IDS, state=['available'])

course_list = []
total_assignments = 0
total_scores = 0

for course in courses:
    try:
        print(f"\n📚 Processing Course: {course.name} (ID: {course.id})")
        course_list.append({"course_id": course.id, "course_name": course.name})
        
        # 1. Fetch all assignments for the course
        assignments = course.get_assignments()
        assign_data = []
        for a in assignments:
            assign_data.append({
                "assignment_id": a.id,
                "course_id": course.id,
                "title": a.name[:250], # Truncate to fit VARCHAR
                "points_possible": getattr(a, 'points_possible', None),
                "due_at": getattr(a, 'due_at', None)
            })
        
        # 2. Fetch ALL submissions for ALL students in one highly optimized API call
        submissions = course.get_multiple_submissions(student_ids=['all'])
        sub_data = []
        for sub in submissions:
            # Skip records for "Test Students" or deleted submissions
            if getattr(sub, 'workflow_state', 'unsubmitted') != 'deleted':
                sub_data.append({
                    "submission_id": sub.id,
                    "assignment_id": sub.assignment_id,
                    "student_id": sub.user_id,
                    "score": getattr(sub, 'score', None),
                    "grade": str(getattr(sub, 'grade', ''))[:50],
                    "workflow_state": getattr(sub, 'workflow_state', None),
                    "submitted_at": getattr(sub, 'submitted_at', None)
                })

        # 3. Write data to MSSQL (Clear old data for this course, then insert fresh)
        with engine.begin() as conn:
            # Upsert Course Data
            conn.execute(text(f"DELETE FROM canvas_active_courses WHERE course_id = {course.id}"))
            conn.execute(text(f"DELETE FROM canvas_assignments WHERE course_id = {course.id}"))
            
            # Submissions are trickier to delete by course_id because the scores table doesn't hold the course_id directly,
            # so we delete submissions where the assignment_id belongs to this course.
            conn.execute(text(f"""
                DELETE FROM canvas_scores 
                WHERE assignment_id IN (SELECT assignment_id FROM canvas_assignments WHERE course_id = {course.id})
            """))

        # Bulk insert the new data using Pandas
        if assign_data:
            pd.DataFrame(assign_data).to_sql('canvas_assignments', con=engine, if_exists='append', index=False)
            total_assignments += len(assign_data)
            
        if sub_data:
            pd.DataFrame(sub_data).to_sql('canvas_scores', con=engine, if_exists='append', index=False)
            total_scores += len(sub_data)
            
        print(f"   ✅ Saved {len(assign_data)} assignments and {len(sub_data)} scores.")
        
    except Exception as e:
        print(f"   ⚠️ Error processing course {course.id}: {e}")

# Save the master course list
if course_list:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE canvas_active_courses"))
    pd.DataFrame(course_list).to_sql('canvas_active_courses', con=engine, if_exists='append', index=False)

print(f"\n🎉 Extraction Complete! Downloaded {total_assignments} assignments and {total_scores} individual scores.")