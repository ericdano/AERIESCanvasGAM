import pandas as pd
import os, sys, shlex, subprocess, gam, json, logging, smtplib, datetime
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from timeit import default_timer as timer
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from collections.abc import Iterable

'''

2026 by Eric Dannewitz
Pulls Grades from Canvas for specified terms and then 

'''
    
WasThereAnErr = False
start_of_timer = timer()
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging server stuff
if configs['logserveraddress'] is None:
    logfilename = Path.home() / ".Acalanes" / configs['logfilename']
    thelogger = logging.getLogger('MyLogger')
    thelogger.basicConfig(filename=str(logfilename), level=thelogger.info)
else:
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)

#-----Canvas Info -------------------
# Change around if you need to use the BETA API
# Canvas_API_URL = configs['CanvasBETAAPIURL']
Canvas_API_URL = configs['CanvasAPIURL']
#----------------------------------------
TARGET_TERM_IDS = [310,312] # put in the terms as Canvas is dumb. Currently Miramonte Year and Spring 2026 for testing

dest_filename = "canvas_2026_grades_export.csv"
os.chdir('E:\\PythonTemp')

Canvas_API_KEY = configs['CanvasAPIKey']
thelogger.info('Canvas Groups for Counselors->Connecting to Canvas')
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)

print("Starting data extraction...")

# We will store everything in a list of dictionaries first
all_grades_data = []

# Loop through each term ID you care about
for term_id in TARGET_TERM_IDS:
    print(f"\n--- Fetching Active Courses for Term ID: {term_id} ---")
    
    # Filter courses by the specific term AND ensure they are published/active
    courses = account.get_courses(
        enrollment_term_id=term_id, 
        state=['available'], 
        include=['teachers']
    )
    
    for course in courses:
        print(f"Processing: {course.name} (ID: {course.id})")
        
        try:
            # 1. Extract Instructor(s)
            teacher_names = []
            if hasattr(course, 'teachers'):
                teacher_names = [t.get('display_name', 'Unknown') for t in course.teachers]
            instructor_string = ", ".join(teacher_names) if teacher_names else "No Instructor Listed"
            
            # 2. Fetch Students and their Enrollments
            users = course.get_users(enrollment_type=['student'], include=['enrollments'])
            
            for user in users:
                if hasattr(user, 'enrollments'):
                    for enrollment in user.enrollments:
                        grades = enrollment.get('grades', {})
                        current_score = grades.get('current_score', 'N/A')
                        current_grade = grades.get('current_grade', 'N/A')
                        
                        # Append the row data as a dictionary
                        all_grades_data.append({
                            'Term ID': term_id,
                            'Course Name': course.name,
                            'Instructor(s)': instructor_string,
                            'Student Name': user.name,
                            'Score': current_score,
                            'Grade': current_grade
                        })
                        
        except Exception as e:
            print(f"  -> Skipping course {course.id} due to error: {e}")

# --- Pandas DataFrame Creation & Export ---
print("\nCompiling data into pandas DataFrame...")
df = pd.DataFrame(all_grades_data)

print(f"Exporting to {dest_filename}...")
df.to_csv(dest_filename, index=False, encoding='utf-8')

target_user = "edannewitz@auhsdschools.org"
google_sheet_id = "1P-OiCMG1sKPixYSo9LjLBoL--uARWLarqTXP2V0gsqk"
stat1 = gam.CallGAMCommand(['gam','user', target_user, 'update','drivefile','drivefilename',google_sheet_id, 'localfile',dest_filename])
if stat1 != 0:  
    WasThereAnError = True
    thelogger.info('Update ASB Works->GAM returned an error from last command')
    #msgbody += f"GAM returned an error from last command on ASB Works upload\n"
    print('GAM Error')
#os.remove(dest_filename)
print("Done! Spreadsheet is ready.")