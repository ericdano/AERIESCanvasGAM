import os
import ssl 
import json
import urllib.parse
import pandas as pd
import streamlit as st
from datetime import datetime
from sqlalchemy import create_engine, inspect
from pathlib import Path
from ldap3 import Server, Connection, ALL, Tls

# --- Setup UI ---
st.set_page_config(page_title="Canvas Grade Extractor", layout="wide")
st.title("Canvas Account-Level Grade Extractor")

# --- Initialize Session State Variables ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None

# State variables to manage the Pop-Up Window logic
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
    
    # AD Configs
    AD_SERVER = configs.get('AD_Server')
    AD_DOMAIN = configs.get('AD_Domain')
    AD_SEARCH_BASE = configs.get('AD_Search_Base')
    AD_REQUIRED_GROUP = configs.get('AD_Required_Group')
    AD_PORT = 636
    AD_USE_SSL = True
    
    if not AD_SERVER or not AD_DOMAIN or not AD_REQUIRED_GROUP:
        st.error(f"Missing critical AD configuration variables in {confighome}")
        st.stop()
        
except FileNotFoundError:
    st.error(f"Configuration file not found at: {confighome}")
    st.stop()
except json.JSONDecodeError:
    st.error(f"The file at {confighome} is not formatted as valid JSON.")
    st.stop()
except Exception as e:
    st.error(f"An error occurred loading the config: {e}")
    st.stop()

# --- Database Connection ---
server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'
db_name = configs.get('CanvasGradesDB')
uid = configs.get('LocalAERIES_Username')
pwd = configs.get('LocalAERIES_Password')

if not db_name or not uid or not pwd:
    st.error("Missing Aeries MSSQL Database credentials in Acalanes.json")
    st.stop()

# Safely encode the connection string for SQLAlchemy
odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)

db_url = f"mssql+pyodbc:///?odbc_connect={params}"
engine = create_engine(db_url)

# --- Helper Function: Check for existing, COMPLETE syncs ---
def get_sync_dates():
    inspector = inspect(engine)
    # Check if BOTH tables exist
    tables = inspector.get_table_names()
    if 'student_grades' in tables and 'sync_history' in tables:
        # Only fetch timestamps that are explicitly marked as COMPLETE
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

# --- Authentication Logic ---
def authenticate_user(username, password):
    tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
    server = Server(AD_SERVER, 
                    port=AD_PORT,
                    use_ssl=AD_USE_SSL,
                    tls=tls_config,
                    get_info=ALL
                )
    user_principal = f"{AD_DOMAIN}\\{username}"
    
    try:
        conn = Connection(server, user=user_principal, password=password, auto_bind=True)
        search_filter = f"(&(objectclass=person)(sAMAccountName={username})(memberOf={AD_REQUIRED_GROUP}))"
        
        conn.search(
            search_base=AD_SEARCH_BASE, 
            search_filter=search_filter, 
            attributes=['sAMAccountName']
        )
        
        if len(conn.entries) > 0:
            return True, "Authentication successful."
        else:
            return False, "Access Denied: You are not a member of the required security group."
            
    except Exception as e:
        return False, f"Authentication failed. AD Error: {str(e)}"

# --- Modal (Pop-Up) Definition ---
@st.dialog("Data Explorer", width="large")
def open_course_modal(course_name, sync_date):
    
    # View 1: Course Roster
    if st.session_state.modal_view == 'roster':
        st.markdown(f"### 📘 Course Roster: {course_name}")
        st.info("👆 **Click the checkbox next to a student** to instantly pull up their full report card.")
        
        query = f"SELECT student_name, current_score, current_grade FROM student_grades WHERE sync_timestamp = '{sync_date}' AND course_name = '{course_name}'"
        course_df = pd.read_sql(query, con=engine)
        
        event = st.dataframe(
            course_df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # If a student is clicked, update state and rerun the modal
        if event.selection.rows:
            row_idx = event.selection.rows[0]
            st.session_state.selected_student = course_df.iloc[row_idx]['student_name']
            st.session_state.modal_view = 'student'
            st.rerun() 
            
    # View 2: Student Report Card
    elif st.session_state.modal_view == 'student':
        student_name = st.session_state.selected_student
        
        if st.button("⬅️ Back to Course Roster"):
            st.session_state.modal_view = 'roster'
            st.rerun()
            
        st.markdown(f"### 🎓 Report Card: {student_name}")
        
        # Pull all advanced metrics when viewing from the Modal
        query = f"""
            SELECT course_name, instructors, current_score, current_grade, 
                   last_access, missing_assignments, zeros, latest_submission 
            FROM student_grades 
            WHERE sync_timestamp = '{sync_date}' 
            AND student_name = '{student_name}'
        """
        student_df = pd.read_sql(query, con=engine)
        
        student_df.rename(columns={
            'course_name': 'Course',
            'instructors': 'Teacher',
            'current_score': 'Score',
            'current_grade': 'Grade',
            'last_access': 'Last Access',
            'missing_assignments': 'Missing',
            'zeros': 'Zeros',
            'latest_submission': 'Latest Submission'
        }, inplace=True)
        
        st.dataframe(
            student_df,
            use_container_width=True,
            hide_index=True
        )

# ==========================================
# UI RENDERING LOGIC
# ==========================================

if not st.session_state.authenticated:
    # --- Show Login Screen ---
    st.subheader("🔒 Active Directory Login")
    st.markdown("Please log in with your network credentials to access Canvas data.")
    
    with st.form("login_form"):
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Log In")
        
        if submit_button:
            if username_input and password_input:
                is_auth, message = authenticate_user(username_input, password_input)
                if is_auth:
                    st.session_state.authenticated = True
                    st.session_state.username = username_input
                    st.rerun() 
                else:
                    st.error(message)
            else:
                st.warning("Please enter both username and password.")

else:
    # --- Show Main Application ---
    st.sidebar.header("Data Sync Setup")
    st.sidebar.success(f"✅ Logged in as: {st.session_state.username}")
    
    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
        
    st.sidebar.info(f"**Account ID:** {ACCOUNT_ID}\n\n**Term IDs:** {', '.join(map(str, TARGET_TERM_IDS))}")

    if not existing_syncs:
        st.info("The database is currently empty. The automated background sync is scheduled to run at 6:30 AM.")
        st.markdown("Please check back after the sync completes.")
    else:
        tab1, tab2, tab3 = st.tabs(["🗄️ Course Viewer", "🔍 Student Search", "📈 Analytics & Trends"])
        
        with tab1:
            st.subheader("Historical Course Viewer")
            selected_sync = st.selectbox(
                "Select a Data Sync Date to View:", 
                options=existing_syncs,
                index=0,
                key="sync_tab1" 
            )
            
            if selected_sync:
                query = f"SELECT course_name, instructors, student_name, current_score FROM student_grades WHERE sync_timestamp = '{selected_sync}'"
                raw_df = pd.read_sql(query, con=engine)
                
                raw_df['current_score'] = pd.to_numeric(raw_df['current_score'], errors='coerce')
                courses_df = raw_df.groupby(['course_name', 'instructors']).agg(
                    total_students=('student_name', 'count'),
                    average_score=('current_score', 'mean')
                ).reset_index()
                courses_df['average_score'] = courses_df['average_score'].round(2)
                
                courses_df.rename(columns={
                    'course_name': 'Course Name',
                    'instructors': 'Instructors',
                    'total_students': 'Total Students',
                    'average_score': 'Average Score (%)'
                }, inplace=True)
                
                st.write(f"Showing **{len(courses_df)}** courses from the sync on: **{selected_sync}**")
                st.info("👆 **Click the checkbox on the far-left of a course** to open its roster.")
                
                event = st.dataframe(
                    courses_df, 
                    use_container_width=True,
                    on_select="rerun", 
                    selection_mode="single-row",
                    hide_index=False
                )
                
                if event.selection.rows:
                    row_idx = event.selection.rows[0]
                    selected_course = courses_df.iloc[row_idx]['Course Name']
                    
                    if st.session_state.current_modal_course != selected_course:
                        st.session_state.current_modal_course = selected_course
                        st.session_state.modal_view = 'roster'
                        
                    open_course_modal(selected_course, selected_sync)

        # --- STUDENT SEARCH ---
        with tab2:
            st.subheader("Student Directory Search")
            selected_sync_student = st.selectbox(
                "Select a Data Sync Date to View:", 
                options=existing_syncs,
                index=0,
                key="sync_tab2" 
            )
            
            if selected_sync_student:
                query_students = f"SELECT DISTINCT student_name FROM student_grades WHERE sync_timestamp = '{selected_sync_student}' ORDER BY student_name"
                students_df = pd.read_sql(query_students, con=engine)
                student_list = ["-- Type or Select a Student --"] + students_df['student_name'].tolist()
                
                selected_student_search = st.selectbox(
                    "Search for a Student:", 
                    options=student_list,
                    key="student_search_box"
                )
                
                if selected_student_search != "-- Type or Select a Student --":
                    st.divider()
                    st.markdown(f"### 🎓 Report Card: {selected_student_search}")
                    
                    query_report = f"""
                        SELECT course_name, instructors, current_score, current_grade, 
                               last_access, missing_assignments, zeros, latest_submission 
                        FROM student_grades 
                        WHERE sync_timestamp = '{selected_sync_student}' 
                        AND student_name = '{selected_student_search}'
                    """
                    report_df = pd.read_sql(query_report, con=engine)
                    
                    report_df.rename(columns={
                        'course_name': 'Course',
                        'instructors': 'Teacher',
                        'current_score': 'Score',
                        'current_grade': 'Grade',
                        'last_access': 'Last Access',
                        'missing_assignments': 'Missing',
                        'zeros': 'Zeros',
                        'latest_submission': 'Latest Submission'
                    }, inplace=True)
                    
                    st.dataframe(
                        report_df,
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    report_df['Score'] = pd.to_numeric(report_df['Score'], errors='coerce')
                    if not report_df['Score'].isna().all():
                        student_avg = report_df['Score'].mean()
                        st.metric("Student's Average Score across all current courses", f"{student_avg:.2f}%")

        with tab3:
            st.subheader("Average Score Trends Over Time")
            st.markdown("Track how the average scores across your selected terms change with each sync.")

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