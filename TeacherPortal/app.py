import os
import json
import urllib.parse
import pandas as pd
import streamlit as st
import jwt
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from pathlib import Path
from streamlit_oauth import OAuth2Component
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- Setup UI ---
st.set_page_config(page_title="Teacher Portal", layout="wide")
st.title("Teacher Portal")

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None

if 'current_modal_course' not in st.session_state:
    st.session_state.current_modal_course = None
if 'modal_view' not in st.session_state:
    st.session_state.modal_view = 'roster'
if 'selected_student' not in st.session_state:
    st.session_state.selected_student = None

# --- Load Configuration ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
try:
    with open(confighome, 'r') as f:
        configs = json.load(f)
        
    ACCOUNT_ID = configs.get('CanvasAccountID', 1) 
    TARGET_TERM_IDS = configs.get('TargetTermIDs')
    
    # Google OAuth Configs
    GOOGLE_CLIENT_ID = configs.get('GoogleClientID')
    GOOGLE_CLIENT_SECRET = configs.get('GoogleClientSecret')
    REDIRECT_URI = configs.get('GoogleRedirectURI')
    ALLOWED_EMAILS = configs.get('AllowedAdminEmails', [])
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        st.error(f"Missing Google OAuth configuration variables in {confighome}")
        st.stop()
        
except Exception as e:
    st.error(f"Config load error: {e}")
    st.stop()

# --- Database Connection ---
server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'
db_name = configs.get('LocalAUHSD')
uid = configs.get('LocalAERIES_Username')
pwd = configs.get('LocalAERIES_Password')

odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# --- Initialize Academy Database Tables ---
def init_academy_db():
    with engine.connect() as conn:
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='academy_sessions' and xtype='U')
            CREATE TABLE academy_sessions (
                session_id INT IDENTITY(1,1) PRIMARY KEY,
                teacher_email VARCHAR(255),
                session_date DATE,
                title VARCHAR(255),
                capacity INT
            )
        """))
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='academy_roster' and xtype='U')
            CREATE TABLE academy_roster (
                roster_id INT IDENTITY(1,1) PRIMARY KEY,
                session_id INT,
                student_id INT,
                student_name VARCHAR(255),
                status VARCHAR(50) DEFAULT 'Registered'
            )
        """))
        conn.commit()

init_academy_db()

def is_user_authorized(user_email):
    # 1. Check manual allowlist first
    if user_email in ALLOWED_EMAILS:
        return True
    
    # 2. Check Google Group via Admin SDK
    try:
        SCOPES = ['https://www.googleapis.com/auth/admin.directory.group.readonly']
        # Load the Service Account credentials
        creds = service_account.Credentials.from_service_account_file(
            configs.get('ServiceAccountFile'), 
            scopes=SCOPES
        ).with_subject(configs.get('AdminEmail')) # Acting as the admin
        
        service = build('admin', 'directory_v1', credentials=creds)
        
        # Ask Google: "Is this user in the group?"
        response = service.members().hasMember(
            groupKey=configs.get('TargetGoogleGroup'), 
            memberKey=user_email
        ).execute()
        
        return response.get('isMember', False)
    except Exception as e:
        st.sidebar.error(f"Group Auth Error: {e}")
        return False

def get_sync_dates():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if 'student_grades' in tables and 'sync_history' in tables:
        query = """
            SELECT DISTINCT g.sync_timestamp 
            FROM student_grades g
            INNER JOIN sync_history h ON g.sync_timestamp = h.sync_timestamp
            WHERE h.status = 'COMPLETE'
            ORDER BY g.sync_timestamp DESC
        """
        try:
            df_dates = pd.read_sql(query, con=engine)
            return df_dates['sync_timestamp'].tolist()
        except Exception:
            return []
    return []

existing_syncs = get_sync_dates()

# --- Modal (Pop-Up) Definition ---
@st.dialog("Data Explorer", width="large")
def open_course_modal(course_name, sync_date):
    
    if st.session_state.modal_view == 'roster':
        st.markdown(f"### 📘 Course Roster: {course_name}")
        st.info("👆 **Click the checkbox next to a student** to instantly pull up their full report card.")
        
        query = f"SELECT student_name, current_score, current_grade, course_id FROM student_grades WHERE sync_timestamp = '{sync_date}' AND course_name = '{course_name}'"
        course_df = pd.read_sql(query, con=engine)
        
        course_df['Course Page'] = "https://acalanes.instructure.com/courses/" + course_df['course_id'].astype(str)
        
        event = st.dataframe(
            course_df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "course_id": None, 
                "Course Page": st.column_config.LinkColumn("Course Page", display_text="Open in Canvas ↗")
            }
        )
        
        if event.selection.rows:
            row_idx = event.selection.rows[0]
            st.session_state.selected_student = course_df.iloc[row_idx]['student_name']
            st.session_state.modal_view = 'student'
            st.rerun() 
            
    elif st.session_state.modal_view == 'student':
        student_name = st.session_state.selected_student
        if st.button("⬅️ Back to Course Roster"):
            st.session_state.modal_view = 'roster'
            st.rerun()
            
        st.markdown(f"### 🎓 Report Card: {student_name}")
        
        query = f"""
            SELECT course_name, instructors, current_score, current_grade, 
                   last_access, missing_assignments, zeros, latest_submission, course_id, student_id
            FROM student_grades 
            WHERE sync_timestamp = '{sync_date}' AND student_name = '{student_name}'
        """
        student_df = pd.read_sql(query, con=engine)
        
        student_df['Course URL'] = "https://acalanes.instructure.com/courses/" + student_df['course_id'].astype(str)
        student_df['Grades URL'] = "https://acalanes.instructure.com/courses/" + student_df['course_id'].astype(str) + "/grades/" + student_df['student_id'].astype(str)
        student_df['Usage URL'] = "https://acalanes.instructure.com/courses/" + student_df['course_id'].astype(str) + "/users/" + student_df['student_id'].astype(str) + "/usage"

        student_df.rename(columns={
            'course_name': 'Course', 'instructors': 'Teacher', 'current_score': 'Score', 'current_grade': 'Grade',
            'last_access': 'Last Access', 'missing_assignments': 'Missing', 'zeros': 'Zeros', 'latest_submission': 'Latest Sub'
        }, inplace=True)
        
        display_columns = ['Course', 'Teacher', 'Score', 'Grade', 'Missing', 'Zeros', 'Latest Sub', 'Last Access', 'Course URL', 'Grades URL', 'Usage URL']
        
        st.dataframe(
            student_df[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Course URL": st.column_config.LinkColumn("Course", display_text="Homepage"),
                "Grades URL": st.column_config.LinkColumn("Grades", display_text="Gradebook"),
                "Usage URL": st.column_config.LinkColumn("Activity", display_text="Access Log")
            }
        )

# ==========================================
# UI RENDERING LOGIC (Google OAuth)
# ==========================================

if not st.session_state.authenticated:
    st.subheader("🔒 Administrator Login")
    
    # Initialize the OAuth2 Component
    oauth2 = OAuth2Component(
        client_id=GOOGLE_CLIENT_ID, 
        client_secret=GOOGLE_CLIENT_SECRET, 
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth", 
        token_endpoint="https://oauth2.googleapis.com/token", 
        refresh_token_endpoint="https://oauth2.googleapis.com/token", 
        revoke_token_endpoint="https://oauth2.googleapis.com/revoke"
    )
    
    # Render the Google Login Button
    result = oauth2.authorize_button(
        name="Sign in with Google",
        redirect_uri=REDIRECT_URI,
        scope="openid email profile",
        icon="https://www.google.com/favicon.ico",
        use_container_width=True
    )
    
    if result and 'token' in result:
        # Decode the secure Google JWT to extract the user's email address
        id_token = result['token']['id_token']
        decoded_token = jwt.decode(id_token, options={"verify_signature": False})
        user_email = decoded_token.get('email')
        
        # The Bouncer: Check the manual list AND the Google Group
        if is_user_authorized(user_email):
            st.session_state.authenticated = True
            st.session_state.username = user_email
            st.rerun()
        else:
            st.error(f"Access Denied: {user_email} is not authorized for this portal.")

else:
    # --- SIDEBAR NAVIGATION ROUTER ---
    st.sidebar.success(f"✅ Logged in as: {st.session_state.username}")
    
    app_mode = st.sidebar.radio("Navigation", ["🗄️ Grade Explorer", "🏫 Academy"])
    st.sidebar.divider()
    
    st.sidebar.header("Data Sync Setup")
    
    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()

    # ==========================================
    # APP MODE 1: GRADE EXPLORER 
    # ==========================================
    if app_mode == "🗄️ Grade Explorer":
        if not existing_syncs:
            st.info("The database is currently empty. Please wait for the initial background sync to complete.")
        else:
            # --- NEW 6-TAB LAYOUT ---
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "🗄️ Course Viewer", 
                "🔍 Student Search", 
                "📈 Analytics", 
                "🚨 At-Risk Watchlist", 
                "👻 Inactivity Monitor", 
                "📊 Grade Distribution"
            ])
            
            with tab1:
                st.subheader("Historical Course Viewer")
                selected_sync = st.selectbox("Select a Data Sync Date:", options=existing_syncs, index=0, key="sync_tab1")
                
                if selected_sync:
                    query = f"SELECT course_name, instructors, student_name, current_score FROM student_grades WHERE sync_timestamp = '{selected_sync}'"
                    raw_df = pd.read_sql(query, con=engine)
                    raw_df['current_score'] = pd.to_numeric(raw_df['current_score'], errors='coerce')
                    
                    courses_df = raw_df.groupby(['course_name', 'instructors']).agg(
                        total_students=('student_name', 'count'),
                        average_score=('current_score', 'mean')
                    ).reset_index()
                    courses_df['average_score'] = courses_df['average_score'].round(2)
                    
                    courses_df.rename(columns={'course_name': 'Course Name', 'instructors': 'Instructors', 'total_students': 'Total Students', 'average_score': 'Avg Score (%)'}, inplace=True)
                    
                    event = st.dataframe(courses_df, use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=False)
                    
                    if event.selection.rows:
                        selected_course = courses_df.iloc[event.selection.rows[0]]['Course Name']
                        if st.session_state.current_modal_course != selected_course:
                            st.session_state.current_modal_course = selected_course
                            st.session_state.modal_view = 'roster'
                        open_course_modal(selected_course, selected_sync)

            with tab2:
                st.subheader("Student Directory Search")
                selected_sync_student = st.selectbox("Select a Data Sync Date:", options=existing_syncs, index=0, key="sync_tab2")
                
                if selected_sync_student:
                    query_students = f"SELECT DISTINCT student_name FROM student_grades WHERE sync_timestamp = '{selected_sync_student}' ORDER BY student_name"
                    students_df = pd.read_sql(query_students, con=engine)
                    student_list = ["-- Type or Select a Student --"] + students_df['student_name'].tolist()
                    
                    selected_student_search = st.selectbox("Search for a Student:", options=student_list, key="student_search_box")
                    
                    if selected_student_search != "-- Type or Select a Student --":
                        st.divider()
                        st.markdown(f"### 🎓 Report Card: {selected_student_search}")
                        
                        query_report = f"""
                            SELECT course_name, instructors, current_score, current_grade, 
                                   last_access, missing_assignments, zeros, latest_submission, course_id, student_id
                            FROM student_grades 
                            WHERE sync_timestamp = '{selected_sync_student}' 
                            AND student_name = '{selected_student_search}'
                        """
                        report_df = pd.read_sql(query_report, con=engine)
                        
                        report_df['Course URL'] = "https://acalanes.instructure.com/courses/" + report_df['course_id'].astype(str)
                        report_df['Grades URL'] = "https://acalanes.instructure.com/courses/" + report_df['course_id'].astype(str) + "/grades/" + report_df['student_id'].astype(str)
                        report_df['Usage URL'] = "https://acalanes.instructure.com/courses/" + report_df['course_id'].astype(str) + "/users/" + report_df['student_id'].astype(str) + "/usage"

                        report_df.rename(columns={
                            'course_name': 'Course', 'instructors': 'Teacher', 'current_score': 'Score', 'current_grade': 'Grade',
                            'last_access': 'Last Access', 'missing_assignments': 'Missing', 'zeros': 'Zeros', 'latest_submission': 'Latest Sub'
                        }, inplace=True)
                        
                        display_cols = ['Course', 'Teacher', 'Score', 'Grade', 'Missing', 'Zeros', 'Latest Sub', 'Last Access', 'Course URL', 'Grades URL', 'Usage URL']
                        
                        st.dataframe(
                            report_df[display_cols],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Course URL": st.column_config.LinkColumn("Course", display_text="Homepage"),
                                "Grades URL": st.column_config.LinkColumn("Grades", display_text="Gradebook"),
                                "Usage URL": st.column_config.LinkColumn("Activity", display_text="Access Log")
                            }
                        )

            with tab3:
                st.subheader("Average Score Trends Over Time")
                all_data_query = "SELECT sync_timestamp, current_score FROM student_grades"
                trend_df = pd.read_sql(all_data_query, con=engine)
                trend_df['current_score'] = pd.to_numeric(trend_df['current_score'], errors='coerce')
                trend_df = trend_df.dropna(subset=['current_score'])

                if not trend_df.empty:
                    avg_scores = trend_df.groupby('sync_timestamp')['current_score'].mean().reset_index()
                    avg_scores = avg_scores.set_index('sync_timestamp')
                    st.line_chart(avg_scores)
                    latest_avg = avg_scores.iloc[-1]['current_score']
                    st.metric(label="Latest Institution Average", value=f"{latest_avg:.2f}%")
                else:
                    st.info("Not enough numeric score data to generate a trend chart yet.")

            # --- TAB 4: INTERVENTION WATCHLIST ---
            with tab4:
                st.subheader("🚨 Intervention Watchlist")
                st.markdown("Identify students who are currently struggling based on their score, and optionally, their missing assignments.")
                selected_sync_risk = st.selectbox("Select a Data Sync Date:", options=existing_syncs, index=0, key="sync_tab4")
                
                # The new toggle switch
                include_missing = st.toggle("Include Missing Assignments in Risk Calculation", value=True)
                
                col1, col2 = st.columns(2)
                score_threshold = col1.slider("Flag Scores Below (%)", 0, 100, 70)
                
                # Conditionally show the second input box based on the toggle
                if include_missing:
                    missing_threshold = col2.number_input("Flag Missing Assignments Greater Than", min_value=0, value=3)
                
                if selected_sync_risk:
                    query = f"""
                        SELECT student_name, course_name, instructors, current_score, current_grade, missing_assignments 
                        FROM student_grades 
                        WHERE sync_timestamp = '{selected_sync_risk}'
                    """
                    df_risk = pd.read_sql(query, con=engine)
                    df_risk['current_score'] = pd.to_numeric(df_risk['current_score'], errors='coerce')
                    df_risk['missing_assignments'] = pd.to_numeric(df_risk['missing_assignments'], errors='coerce')
                    
                    # Apply conditional filtering based on the toggle state
                    if include_missing:
                        filtered_risk = df_risk[
                            (df_risk['current_score'] < score_threshold) | 
                            (df_risk['missing_assignments'] > missing_threshold)
                        ]
                    else:
                        filtered_risk = df_risk[
                            (df_risk['current_score'] < score_threshold)
                        ]
                    
                    filtered_risk.rename(columns={
                        'student_name': 'Student', 'course_name': 'Course', 'instructors': 'Teacher', 
                        'current_score': 'Score', 'current_grade': 'Grade', 'missing_assignments': 'Missing'
                    }, inplace=True)
                    
                    st.warning(f"Found {len(filtered_risk)} at-risk enrollments.")
                    st.dataframe(filtered_risk, use_container_width=True, hide_index=True)
            
            # --- TAB 5: INACTIVITY MONITOR ---
            with tab5:
                st.subheader("👻 Inactivity Monitor")
                st.markdown("Find students who have not logged into their Canvas course recently.")
                selected_sync_inactive = st.selectbox("Select a Data Sync Date:", options=existing_syncs, index=0, key="sync_tab5")
                
                days_inactive_threshold = st.slider("Flag Students Inactive For (Days)", 1, 30, 7)
                
                if selected_sync_inactive:
                    query = f"""
                        SELECT student_name, course_name, last_access
                        FROM student_grades 
                        WHERE sync_timestamp = '{selected_sync_inactive}'
                    """
                    df_inactive = pd.read_sql(query, con=engine)
                    sync_dt = datetime.strptime(selected_sync_inactive, "%Y-%m-%d %H:%M:%S")
                    
                    def calc_inactive(row):
                        if row['last_access'] == 'Never' or pd.isna(row['last_access']):
                            return 999 # Use 999 to represent 'Never'
                        try:
                            access_dt = datetime.strptime(row['last_access'], "%b %d, %Y")
                            return (sync_dt - access_dt).days
                        except:
                            return 0
                    
                    df_inactive['Days Inactive'] = df_inactive.apply(calc_inactive, axis=1)
                    filtered_inactive = df_inactive[df_inactive['Days Inactive'] >= days_inactive_threshold].copy()
                    
                    filtered_inactive['Status'] = filtered_inactive['Days Inactive'].apply(
                        lambda x: 'Never Logged In' if x == 999 else f"{x} Days"
                    )
                    
                    filtered_inactive.rename(columns={'student_name': 'Student', 'course_name': 'Course', 'last_access': 'Last Access Date'}, inplace=True)
                    
                    st.info(f"Found {len(filtered_inactive)} inactive enrollments.")
                    st.dataframe(filtered_inactive[['Student', 'Course', 'Last Access Date', 'Status']], use_container_width=True, hide_index=True)

            # --- TAB 6: GRADE DISTRIBUTION ---
            with tab6:
                st.subheader("📊 Grade Distribution (School-Wide)")
                selected_sync_dist = st.selectbox("Select a Data Sync Date:", options=existing_syncs, index=0, key="sync_tab6")
                
                if selected_sync_dist:
                    query = f"SELECT current_grade FROM student_grades WHERE sync_timestamp = '{selected_sync_dist}'"
                    df_grades = pd.read_sql(query, con=engine)
                    
                    # Clean out blanks and NaNs
                    df_grades = df_grades.dropna(subset=['current_grade'])
                    df_grades = df_grades[df_grades['current_grade'].str.strip() != '']
                    
                    if not df_grades.empty:
                        grade_counts = df_grades['current_grade'].value_counts().reset_index()
                        grade_counts.columns = ['Grade', 'Total Students']
                        
                        # Sort alphabetically to roughly group A, B, C, D, F
                        grade_counts = grade_counts.sort_values(by='Grade')
                        
                        st.bar_chart(grade_counts.set_index('Grade'))
                        
                        with st.expander("View Raw Grade Data"):
                            st.dataframe(grade_counts, hide_index=True)
                    else:
                        st.info("No letter grade data available for this sync.")

    # ==========================================
    # APP MODE 2: ACADEMY (Teachmore Clone)
    # ==========================================
    elif app_mode == "🏫 Academy":
        st.header("Academy Management")
        
        acad_tab1, acad_tab2, acad_tab3 = st.tabs(["📝 Create Session", "🧑‍🎓 Manage Roster", "✅ Check-In / Out"])
        
        # --- ACADEMY TAB 1: CREATE SESSION ---
        with acad_tab1:
            st.subheader("Schedule a New Academy Session")
            with st.form("create_academy_form"):
                col1, col2 = st.columns(2)
                session_date = col1.date_input("Academy Date")
                title = col2.text_input("Session Title / Topic")
                capacity = st.number_input("Max Student Capacity", min_value=1, value=30)
                
                if st.form_submit_button("Create Session"):
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO academy_sessions (teacher_email, session_date, title, capacity)
                            VALUES (:email, :date, :title, :cap)
                        """), {"email": st.session_state.username, "date": session_date, "title": title, "cap": capacity})
                    st.success(f"Session '{title}' created successfully!")
            
            st.divider()
            st.markdown("#### Your Upcoming Sessions")
            try:
                my_sessions = pd.read_sql(f"SELECT session_id, session_date, title, capacity FROM academy_sessions WHERE teacher_email = '{st.session_state.username}' ORDER BY session_date DESC", con=engine)
                st.dataframe(my_sessions, hide_index=True, use_container_width=True)
            except Exception:
                st.info("No sessions created yet.")
                my_sessions = pd.DataFrame()

        # --- ACADEMY TAB 2: MANAGE ROSTER ---
        with acad_tab2:
            st.subheader("Add Students to an Academy")
            if not my_sessions.empty:
                session_dict = dict(zip(my_sessions['session_id'], my_sessions['title'] + " (" + my_sessions['session_date'].astype(str) + ")"))
                selected_session_id = st.selectbox("Select Session:", options=session_dict.keys(), format_func=lambda x: session_dict[x])
                
                st.markdown("**Search Aeries Database:**")
                search_term = st.text_input("Search Student by Name (e.g., Smith):")
                
                if search_term:
                    try:
                        # Assuming STU table uses 'ID' for student number and 'NM' for name
                        aeries_query = f"SELECT ID as student_id, NM as student_name FROM STU WHERE NM LIKE '%{search_term}%' AND DEL = 0"
                        search_results = pd.read_sql(aeries_query, con=engine)
                        
                        if not search_results.empty:
                            event = st.dataframe(search_results, on_select="rerun", selection_mode="multi-row", hide_index=True)
                            
                            if st.button("Add Selected Students to Roster"):
                                if event.selection.rows:
                                    with engine.begin() as conn:
                                        for row_idx in event.selection.rows:
                                            student_id = int(search_results.iloc[row_idx]['student_id'])
                                            student_name = str(search_results.iloc[row_idx]['student_name'])
                                            
                                            check = conn.execute(text(f"SELECT * FROM academy_roster WHERE session_id = {selected_session_id} AND student_id = {student_id}")).fetchone()
                                            if not check:
                                                conn.execute(text("""
                                                    INSERT INTO academy_roster (session_id, student_id, student_name)
                                                    VALUES (:sid, :stid, :sname)
                                                """), {"sid": selected_session_id, "stid": student_id, "sname": student_name})
                                    st.success("Students added to the roster!")
                                    st.rerun()
                                else:
                                    st.warning("Please select at least one student from the table.")
                        else:
                            st.info("No students found in Aeries.")
                    except Exception as e:
                        st.error(f"Error querying Aeries Database: {e}. Check your STU table column names.")
            else:
                st.warning("You need to create a session first.")

        # --- ACADEMY TAB 3: CHECK-IN / OUT ---
        with acad_tab3:
            st.subheader("Live Attendance")
            if not my_sessions.empty:
                checkin_session_id = st.selectbox("Select Session for Attendance:", options=session_dict.keys(), format_func=lambda x: session_dict[x], key="checkin_box")
                
                roster_df = pd.read_sql(f"SELECT roster_id, student_id, student_name, status FROM academy_roster WHERE session_id = {checkin_session_id}", con=engine)
                
                if not roster_df.empty:
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        event = st.dataframe(roster_df[['student_name', 'student_id', 'status']], on_select="rerun", selection_mode="single-row", hide_index=True, use_container_width=True)
                    
                    with col2:
                        st.markdown("**Update Status**")
                        if event.selection.rows:
                            selected_roster_id = int(roster_df.iloc[event.selection.rows[0]]['roster_id'])
                            selected_name = roster_df.iloc[event.selection.rows[0]]['student_name']
                            
                            st.info(f"Student: {selected_name}")
                            
                            if st.button("🟢 Check-In", use_container_width=True):
                                with engine.begin() as conn:
                                    conn.execute(text(f"UPDATE academy_roster SET status = 'Checked In' WHERE roster_id = {selected_roster_id}"))
                                st.rerun()
                                
                            if st.button("🔴 Check-Out", use_container_width=True):
                                with engine.begin() as conn:
                                    conn.execute(text(f"UPDATE academy_roster SET status = 'Checked Out' WHERE roster_id = {selected_roster_id}"))
                                st.rerun()
                                
                            if st.button("⚪ Reset to Registered", use_container_width=True):
                                with engine.begin() as conn:
                                    conn.execute(text(f"UPDATE academy_roster SET status = 'Registered' WHERE roster_id = {selected_roster_id}"))
                                st.rerun()
                        else:
                            st.write("👈 Select a student to update.")
                else:
                    st.info("No students registered for this session yet.")