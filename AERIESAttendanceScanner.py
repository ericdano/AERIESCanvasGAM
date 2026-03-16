import requests
import pandas as pd
import os, sys, shlex, gam, subprocess, json, logging, smtplib, datetime
from email.message import EmailMessage
from pathlib import Path
from timeit import default_timer as timer

# --- Aeries Configuration ---
AERIES_BASE_URL = ""
API_CERTIFICATE = ""
ACADEMIC_YEAR = "2025-2026"   
ABSENCE_THRESHOLD = 1         
SENDER_EMAIL = "auhsdabscencereporter@auhsdschools.org  "
# List of all school codes you want to scan
SCHOOL_CODES = [1, 2, 3, 4]
SCHOOL_NAMES = {1: "Las Lomas High School",
                2: "Acalanes High School",
                3: "Miramonte High School",
                4: "Campolindo High School"}

# --- Email Configuration ---
SMTP_SERVER = "" 
SMTP_PORT = 25                


# --- Admin Lookup Table ---
# Map EVERY school code in your list to the appropriate Administrator's email.
ADMIN_TABLE = {
    1: "edannewitz@auhsdschools.org",
    2: "edannewitz@auhsdschools.org",
    3: "edannewitz@auhsdschools.org",
    4: "edannewitz@auhsdschools.org"
}


DEFAULT_ADMIN_EMAIL = "edannewitz@auhsdschools.org"
HEADERS = {
    "Aeries-Cert": API_CERTIFICATE,
    "Content-Type": "application/json"
}

def fetch_aeries_data(endpoint_url):
    """Fetches data from any Aeries endpoint."""
    try:
        response = requests.get(endpoint_url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if response.status_code != 404:
             print(f"  -> Error connecting to API at {endpoint_url}: {e}")
        return None

def send_email(subject, html_content, recipient_email, cc_email=None):
    """Sends an HTML email."""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = 'edannewitz@auhsdschools.org'  # For testing, we send all emails to the default admin. Change this to recipient_email in production.
    """
    msg['To'] = recipient_email
    
    if cc_email:
        msg['Cc'] = cc_email
    """
    msg.set_content("Please enable HTML to view this message.")
    msg.add_alternative(html_content, subtype='html')

    print(f"  -> Sending email to {recipient_email}...")
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.send_message(msg)
    except Exception as e:
        print(f"  -> Error sending email to {recipient_email}: {e}")

def main():
    global AERIES_BASE_URL, API_CERTIFICATE, SMTP_SERVER
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
      configs = json.load(f)
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    # Grab the configs we need and put them in the global variables
    SMTP_SERVER = configs['SMTPServerAddress']
    AERIES_BASE_URL = configs['AERIES_API_URL']
    API_CERTIFICATE = configs['AERIES_API']
    # ------------
    all_attendance_dfs = []
    all_students_dfs = []
    all_staff_dfs = []

    # 1. Loop Through All Schools to Collect Data
    for school in SCHOOL_CODES:
        print(f"\nScanning School Code: {school}...")
        
        school_has_issues = False
        
        # Check Attendance First
        att_url = f"{AERIES_BASE_URL}/schools/{school}/AttendanceHistory/summary/year/{ACADEMIC_YEAR}"
        raw_att = fetch_aeries_data(att_url)
        
        if raw_att:
            temp_att = pd.DataFrame(raw_att)
            if 'TotalDaysAbsent' in temp_att.columns:
                temp_att['TotalDaysAbsent'] = pd.to_numeric(temp_att['TotalDaysAbsent'])
                flagged_temp = temp_att[temp_att['TotalDaysAbsent'] >= ABSENCE_THRESHOLD].copy()
                
                # If we found students over the threshold, flag it and save the data
                if not flagged_temp.empty:
                    school_has_issues = True
                    flagged_temp['SchoolCode'] = school 
                    all_attendance_dfs.append(flagged_temp)

        # 2. Per-School "All Clear" Routing
        if not school_has_issues:
            print(f"  -> No issues found for School {school}. Sending 'All Clear' to site admin.")
            
            # Look up this specific school's admin
            site_admin_email = ADMIN_TABLE.get(school, DEFAULT_ADMIN_EMAIL)
            subject = f"Attendance Report: No Issues Found Today at {SCHOOL_NAMES[school]}"
            html_body = f"""
            <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2>System Update: Attendance Check</h2>
                    <p>Great news! A scan of the Aeries database found <strong>zero</strong> students exceeding the {ABSENCE_THRESHOLD}-absence threshold at {SCHOOL_NAMES[school]} today.</p>
                    <p>No further action is required.</p>
                </body>
            </html>
            """
            send_email(subject, html_body, site_admin_email)
            
            # Skip fetching students/staff for this school, move to the next one
            continue 
        
        # 3. Fetch Students & Staff (ONLY if the school had issues)
        print("  -> Issues found. Fetching student and staff data...")
        stu_url = f"{AERIES_BASE_URL}/schools/{school}/students"
        raw_stu = fetch_aeries_data(stu_url)
        if raw_stu:
            all_students_dfs.append(pd.DataFrame(raw_stu))

        staff_url = f"{AERIES_BASE_URL}/schools/{school}/staff"
        raw_staff = fetch_aeries_data(staff_url)
        if raw_staff:
            all_staff_dfs.append(pd.DataFrame(raw_staff))

    # 4. Process Action Alerts for Schools With Issues
    if not all_attendance_dfs:
        print("\nFinished! All sites were clear today.")
        return # The loop already sent the clear emails, so we just end the script here.
        
    print("\nProcessing Action Alerts for affected schools...")
    flagged_df = pd.concat(all_attendance_dfs, ignore_index=True)
    df_students = pd.concat(all_students_dfs, ignore_index=True)
    
    if all_staff_dfs:
        df_staff = pd.concat(all_staff_dfs, ignore_index=True)
        df_staff = df_staff[['ID', 'FirstName', 'LastName', 'EmailAddress']]
        df_staff = df_staff.rename(columns={'ID': 'CounselorNumber', 'FirstName': 'StaffFirst', 'LastName': 'StaffLast'})
        df_staff = df_staff.drop_duplicates(subset=['CounselorNumber'])
    else:
        print("Critical Error: Could not load staff data. Exiting.")
        return

    # Merge Data 
    merged_df = pd.merge(flagged_df, df_students, on=['StudentID', 'SchoolCode'], how='left')
    merged_df['CounselorNumber'] = pd.to_numeric(merged_df.get('CounselorNumber', 0), errors='coerce')
    df_staff['CounselorNumber'] = pd.to_numeric(df_staff['CounselorNumber'], errors='coerce')
    final_df = pd.merge(merged_df, df_staff, on='CounselorNumber', how='left')

    # Map the Admin Email 
    final_df['SchoolCode'] = pd.to_numeric(final_df['SchoolCode'], errors='coerce')
    final_df['AdminEmail'] = final_df['SchoolCode'].map(ADMIN_TABLE)

    final_df['EmailAddress'] = final_df['EmailAddress'].fillna(DEFAULT_ADMIN_EMAIL)
    final_df['AdminEmail'] = final_df['AdminEmail'].fillna(DEFAULT_ADMIN_EMAIL)     
    final_df['StaffLast'] = final_df['StaffLast'].fillna('Unassigned')

    columns_to_keep = ['SchoolCode', 'StudentID', 'FirstName', 'LastName', 'Grade', 'TotalDaysAbsent']
    report_columns = [col for col in columns_to_keep if col in final_df.columns]
    
    # Group and Send Action Alert Emails
    for (counselor_email, admin_email), counselor_df in final_df.groupby(['EmailAddress', 'AdminEmail']):
        
        counselor_name = counselor_df['StaffLast'].iloc[0] 
        counselor_df = counselor_df[report_columns].sort_values(by='TotalDaysAbsent', ascending=False)
        
        subject = f"Action Required: Your Students with {ABSENCE_THRESHOLD}+ Absences"
        html_table = f"""
        <html>
            <head>
                <style>
                    table {{ border-collapse: collapse; width: 90%; font-family: Arial, sans-serif; }}
                    th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                    th {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h2>Attendance Alert for Counselor: {counselor_name}</h2>
                <p>The following students on your caseload have <strong>{ABSENCE_THRESHOLD} or more</strong> absences.</p>
                <p><em>Notice: The site administrator ({admin_email}) has been copied on this alert.</em></p>
                {counselor_df.to_html(index=False, justify='left')}
            </body>
        </html>
        """
        send_email(subject, html_table, counselor_email, admin_email)
        
    print("\nAll dynamic targeted emails sent successfully!")

if __name__ == "__main__":
    main()