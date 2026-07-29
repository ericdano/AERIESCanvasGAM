import json
import time
from pathlib import Path
from canvasapi import Canvas

# ==========================================
# 1. SETUP AND CREDENTIALS
# ==========================================
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
    configs = json.load(f)

API_URL = configs['CanvasAPIURL']
API_KEY = configs['CanvasAPIKey']
canvas = Canvas(API_URL, API_KEY)

# Target the main account associated with your API token
account = canvas.get_account(1) 

TEMPLATE_COURSE_CODE = "CHS 2026-27"
TARGET_TERM_ID = 421

# ==========================================
# 2. FIND THE TEMPLATE COURSE
# ==========================================
print(f"Searching for template course: {TEMPLATE_COURSE_CODE}...")
source_course = None
search_results = account.get_courses(search_term=TEMPLATE_COURSE_CODE)

for course in search_results:
    if hasattr(course, 'course_code') and course.course_code == TEMPLATE_COURSE_CODE:
        source_course = course
        break

if not source_course:
    print(f"Error: Could not find '{TEMPLATE_COURSE_CODE}'. Check the course code.")
    exit()

print(f"Found Template Course: {source_course.name} (ID: {source_course.id})")

# ==========================================
# 3. FETCH ALL TARGET COURSES IN TERM
# ==========================================
print(f"\nFetching all courses in term ID {TARGET_TERM_ID}...")
# Added the state array to guarantee we catch published AND unpublished courses
term_courses = account.get_courses(
    enrollment_term_id=TARGET_TERM_ID,
    state=['created', 'claimed', 'available', 'completed']
)

# ==========================================
# 4. INITIATE RESETS AND COPIES
# ==========================================
print("\n--- INITIATING RESETS & COPIES ---")
active_jobs = []

for target in term_courses:
    # Skip the template course itself just in case it lives in term 417
    if target.id == source_course.id:
        continue 

    print(f"Resetting and queueing copy for: {target.name} (Old ID: {target.id})...")
    
    try:
        # Step A: Reset the course (wipes it clean and returns the newly generated course)
        clean_course = target.reset()
        print(f"  -> Reset successful. New Course ID is: {clean_course.id}")
        
        # Step B: Start the migration into the NEW clean course
        migration = clean_course.create_content_migration(
            'course_copy_importer',
            settings={'source_course_id': source_course.id}
        )
        
        # Store the NEW course and its migration object for the monitoring phase
        active_jobs.append({
            'course': clean_course, 
            'migration_id': migration.id
        })
        
    except Exception as e:
        print(f"  -> [ERROR] Failed resetting or copying {target.name}: {e}")
        continue
    
    # A tiny pause prevents hitting Canvas API rate limits
    time.sleep(0.5) 

if not active_jobs:
    print("\nNo valid target courses were processed. Exiting script.")
    exit()

print(f"\nSuccessfully queued {len(active_jobs)} courses. Canvas is now processing them.")

# ==========================================
# 5. MONITOR PROGRESS
# ==========================================
print("\n--- MONITORING PROGRESS ---")

# Keep looping as long as there are jobs left in the active list
while len(active_jobs) > 0:
    print(f"\nChecking status of {len(active_jobs)} remaining courses...")
    
    # Iterate over a copy of the list [:] so we can safely remove finished jobs
    for job in active_jobs[:]:
        course = job['course']
        mig_id = job['migration_id']
        
        try:
            # Fetch the updated migration status from Canvas
            updated_migration = course.get_content_migration(mig_id)
            status = updated_migration.workflow_state
            
            if status == 'completed':
                print(f"  [SUCCESS] {course.name} finished copying.")
                active_jobs.remove(job) 
                
            elif status == 'failed':
                print(f"  [FAILED] {course.name} encountered an error during copy.")
                active_jobs.remove(job) 
                
        except Exception as e:
            print(f"  [ERROR] Could not check status for {course.name}: {e}")
            
        # Tiny pause between checks to respect API rate limits
        time.sleep(0.2)
    
    # If there are still jobs running, wait 15 seconds before polling them all again
    if len(active_jobs) > 0:
        print("Waiting 15 seconds before next status check...")
        time.sleep(15)

print("\nAll course resets and copies have completed! Script finished.")