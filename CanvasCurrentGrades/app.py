import os
import json
import urllib.parse
import pandas as pd
import streamlit as st
import jwt
from datetime import datetime
from sqlalchemy import create_engine, inspect
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
db_name = configs.get('CanvasDatabase')
uid = configs.get('LocalAERIES_Username')
pwd = configs.get('LocalAERIES_Password')

odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

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
    st.sidebar.header("Data Sync Setup")
    st.sidebar.success(f"✅ Logged in as: {st.session_state.username}")
    
    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
        
    if not existing_syncs:
        st.info("The database is currently empty. Please wait for the initial background sync to complete.")
    else:
        tab1, tab2, tab3 = st.tabs(["🗄️ Course Viewer", "🔍 Student Search", "📈 Analytics & Trends"])
        
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
                    
                    report_df['Score'] = pd.to_numeric(report_df['Score'], errors='coerce')
                    if not report_df['Score'].isna().all():
                        student_avg = report_df['Score'].mean()
                        st.metric("Student's Average Score", f"{student_avg:.2f}%")

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