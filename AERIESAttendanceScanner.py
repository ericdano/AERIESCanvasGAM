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
ABSENCE_THRESHOLD = 5         
SENDER_EMAIL = "auhsdabscencereporter@auhsdschools.org  "
# List of all school codes you want to scan
SCHOOL_CODES = [1, 2, 3, 4]

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
        print(f"  -> Error connecting to API: {e}")
        return None

def send_email_report(html_content, recipient_email, cc_email, counselor_name):
    """Sends a targeted email to a counselor and CCs the school admin."""
    msg = EmailMessage()
    msg['Subject'] = f"Action Required: Your Students with {ABSENCE_THRESHOLD}+ Absences"
    msg['From'] = SENDER_EMAIL
    #msg['To'] = recipient_email
    #msg['Cc'] = cc_email
    # comment out these two if NOT testing
    msg['To'] = "edannewitz@auhsdschools.org"
    html_content += recipient_email + " and CC: " + cc_email + " and Counselor Name: " + counselor_name + " and Absence Threshold: " + str(ABSENCE_THRESHOLD) + "<br><br>"
    #
    msg.set_content("Please enable HTML to view this message.")
    msg.add_alternative(html_content, subtype='html')

    print(f"  -> Sending report for {counselor_name} to {recipient_email} (CC: {cc_email})...")
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            #server.login(SENDER_EMAIL, SENDER_PASSWORD)
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
    SMTP_SERVER = configs['SMTPServerAddress']
    AERIES_BASE_URL = configs['AERIES_API_URL']
    API_CERTIFICATE = configs['AERIES_API']

    # 1. Fetch Staff Data Once (District-wide)
    print("Fetching district staff data...")
    staff_url = f"{AERIES_BASE_URL}/staff"
    raw_staff = fetch_aeries_data(staff_url)
    if not raw_staff: 
        print("Critical Error: Could not load staff data. Exiting.")
        return
        
    df_staff = pd.DataFrame(raw_staff)
    df_staff = df_staff[['ID', 'FirstName', 'LastName', 'EmailAddress']]
    df_staff = df_staff.rename(columns={'ID': 'CounselorNumber', 'FirstName': 'StaffFirst', 'LastName': 'StaffLast'})

    # 2. Loop Through All Schools to Collect Data
    all_attendance_dfs = []
    all_students_dfs = []

    for school in SCHOOL_CODES:
        print(f"\nFetching data for School Code: {school}...")
        
        # Attendance
        att_url = f"{AERIES_BASE_URL}/schools/{school}/AttendanceHistory/summary/year/{ACADEMIC_YEAR}"
        raw_att = fetch_aeries_data(att_url)
        
        if raw_att:
            temp_att = pd.DataFrame(raw_att)
            if 'TotalDaysAbsent' in temp_att.columns:
                temp_att['TotalDaysAbsent'] = pd.to_numeric(temp_att['TotalDaysAbsent'])
                # Filter immediately to save memory
                flagged_temp = temp_att[temp_att['TotalDaysAbsent'] >= ABSENCE_THRESHOLD].copy()
                
                if not flagged_temp.empty:
                    # Explicitly inject the school code just in case the API omits it
                    flagged_temp['SchoolCode'] = school 
                    all_attendance_dfs.append(flagged_temp)
        
        # Students
        stu_url = f"{AERIES_BASE_URL}/schools/{school}/students"
        raw_stu = fetch_aeries_data(stu_url)
        if raw_stu:
            all_students_dfs.append(pd.DataFrame(raw_stu))

    # 3. Combine Data and Check for Empty Results
    if not all_attendance_dfs:
        print("\nGreat news: No students exceeded the attendance threshold across any schools today.")
        return
        
    # pd.concat stacks all the lists of dataframes on top of each other
    flagged_df = pd.concat(all_attendance_dfs, ignore_index=True)
    df_students = pd.concat(all_students_dfs, ignore_index=True)

    # 4. Merge Data (Attendance -> Students -> Staff)
    print("\nMerging district data...")
    merged_df = pd.merge(flagged_df, df_students, on=['StudentID', 'SchoolCode'], how='left')

    merged_df['CounselorNumber'] = pd.to_numeric(merged_df.get('CounselorNumber', 0), errors='coerce')
    df_staff['CounselorNumber'] = pd.to_numeric(df_staff['CounselorNumber'], errors='coerce')

    final_df = pd.merge(merged_df, df_staff, on='CounselorNumber', how='left')

    # 5. Map the Admin Email using the School Code
    final_df['SchoolCode'] = pd.to_numeric(final_df['SchoolCode'], errors='coerce')
    final_df['AdminEmail'] = final_df['SchoolCode'].map(ADMIN_TABLE)

    # Clean up empty values
    final_df['EmailAddress'] = final_df['EmailAddress'].fillna(DEFAULT_ADMIN_EMAIL)
    final_df['AdminEmail'] = final_df['AdminEmail'].fillna(DEFAULT_ADMIN_EMAIL)     
    final_df['StaffLast'] = final_df['StaffLast'].fillna('Unassigned')

    # Add SchoolCode to the visual report
    columns_to_keep = ['SchoolCode', 'StudentID', 'FirstName', 'LastName', 'Grade', 'TotalDaysAbsent']
    report_columns = [col for col in columns_to_keep if col in final_df.columns]
    
    # 6. Group by BOTH Counselor Email and Admin Email
    print("Processing counselor/admin groups and sending emails...")
    
    for (counselor_email, admin_email), counselor_df in final_df.groupby(['EmailAddress', 'AdminEmail']):
        
        counselor_name = counselor_df['StaffLast'].iloc[0] 
        counselor_df = counselor_df[report_columns].sort_values(by='TotalDaysAbsent', ascending=False)
        
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
        
        send_email_report(html_table, counselor_email, admin_email, counselor_name)
        
    print("\nAll dynamic targeted emails sent successfully!")

if __name__ == "__main__":
    main()
