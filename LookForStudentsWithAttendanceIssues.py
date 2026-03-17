import requests
import pandas as pd
import smtplib
from email.message import EmailMessage

# --- Aeries Configuration ---
AERIES_BASE_URL = "https://yourdistrict.aeries.net/api/v5"
API_CERTIFICATE = "YOUR_API_CERTIFICATE_HERE"
# Note: If running for multiple schools, you'd loop through a list of codes instead of hardcoding one.
SCHOOL_CODE = "123"           
ACADEMIC_YEAR = "2025-2026"   
ABSENCE_THRESHOLD = 5         

# --- Email Configuration ---
SMTP_SERVER = "smtp.gmail.com" 
SMTP_PORT = 465                
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "YOUR_APP_PASSWORD_HERE" 

# --- Admin Lookup Table ---
# Map the School Code to the appropriate Administrator's email.
ADMIN_TABLE = {
    123: "principal_highschool@district.edu",
    124: "principal_middleschool@district.edu",
    125: "principal_elementary@district.edu"
}

DEFAULT_ADMIN_EMAIL = "district_attendance_clerk@district.edu"

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
        print(f"Error connecting to API at {endpoint_url}: {e}")
        return None

def send_email_report(html_content, recipient_email, cc_email, counselor_name):
    """Sends a targeted email to a counselor and CCs the school admin."""
    msg = EmailMessage()
    msg['Subject'] = f"Action Required: Your Students with {ABSENCE_THRESHOLD}+ Absences"
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient_email
    msg['Cc'] = cc_email
    
    msg.set_content("Please enable HTML to view this message.")
    msg.add_alternative(html_content, subtype='html')

    print(f"Sending report for {counselor_name} to {recipient_email} (CC: {cc_email})...")
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {e}")

def main():
    # 1. Fetch Attendance and Filter
    print("Fetching attendance data...")
    att_url = f"{AERIES_BASE_URL}/schools/{SCHOOL_CODE}/AttendanceHistory/summary/year/{ACADEMIC_YEAR}"
    raw_attendance = fetch_aeries_data(att_url)
    if not raw_attendance: return
    
    df_att = pd.DataFrame(raw_attendance)
    if 'TotalDaysAbsent' not in df_att.columns: return
    
    df_att['TotalDaysAbsent'] = pd.to_numeric(df_att['TotalDaysAbsent'])
    flagged_df = df_att[df_att['TotalDaysAbsent'] >= ABSENCE_THRESHOLD]

    if flagged_df.empty:
        print("No students exceeded the attendance threshold today.")
        return

    # 2. Fetch Student Demographics (This includes SchoolCode)
    print("Fetching student demographic data...")
    stu_url = f"{AERIES_BASE_URL}/schools/{SCHOOL_CODE}/students"
    raw_students = fetch_aeries_data(stu_url)
    if not raw_students: return
    df_students = pd.DataFrame(raw_students)

    # 3. Fetch Staff Data
    print("Fetching staff data...")
    staff_url = f"{AERIES_BASE_URL}/staff"
    raw_staff = fetch_aeries_data(staff_url)
    if not raw_staff: return
    df_staff = pd.DataFrame(raw_staff)

    df_staff = df_staff[['ID', 'FirstName', 'LastName', 'EmailAddress']]
    df_staff = df_staff.rename(columns={'ID': 'CounselorNumber', 'FirstName': 'StaffFirst', 'LastName': 'StaffLast'})

    # 4. Merge Data (Attendance -> Students -> Staff)
    merged_df = pd.merge(flagged_df, df_students, on='StudentID', how='left')

    merged_df['CounselorNumber'] = pd.to_numeric(merged_df.get('CounselorNumber', 0), errors='coerce')
    df_staff['CounselorNumber'] = pd.to_numeric(df_staff['CounselorNumber'], errors='coerce')

    final_df = pd.merge(merged_df, df_staff, on='CounselorNumber', how='left')

    # 5. Map the Admin Email using the School Code
    # Ensure SchoolCode is numeric so it matches our ADMIN_TABLE dictionary keys
    final_df['SchoolCode'] = pd.to_numeric(final_df['SchoolCode'], errors='coerce')
    
    # .map() checks the SchoolCode against our dictionary and creates a new column with the Admin Email
    final_df['AdminEmail'] = final_df['SchoolCode'].map(ADMIN_TABLE)

    # Clean up empty values
    final_df['EmailAddress'] = final_df['EmailAddress'].fillna(DEFAULT_ADMIN_EMAIL) # Counselor fallback
    final_df['AdminEmail'] = final_df['AdminEmail'].fillna(DEFAULT_ADMIN_EMAIL)     # Admin fallback
    final_df['StaffLast'] = final_df['StaffLast'].fillna('Unassigned')

    # Add SchoolCode to the visual report
    columns_to_keep = ['SchoolCode', 'StudentID', 'FirstName', 'LastName', 'Grade', 'TotalDaysAbsent']
    report_columns = [col for col in columns_to_keep if col in final_df.columns]
    
    # 6. Group by BOTH Counselor Email and Admin Email
    print("\nProcessing counselor/admin groups...")
    
    # Grouping by both ensures that if a counselor somehow has students at two different schools, 
    # they get separate emails so the correct admin is CC'd on each one.
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