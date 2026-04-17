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
        
except Exception as e:
    st.error(f"Config load error: {e}")
    st.stop()

# --- Database Connection ---
server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'
db_name = configs.get('LocalAERIES_Cambium_DB')
uid = configs.get('LocalAERIES_Username')
pwd = configs.get('LocalAERIES_Password')

odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
params = urllib.parse.quote_plus(odbc_str)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

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

def authenticate_user(username, password):
    tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
    server = Server(AD_SERVER, port=AD_PORT, use_ssl=AD_USE_SSL, tls=tls_config, get_info=ALL)
    user_principal = f"{AD_DOMAIN}\\{username}"
    try:
        conn = Connection(server, user=user_principal, password=password, auto_bind=True)
        search_filter = f"(&(objectclass=person)(sAMAccountName={username})(memberOf={AD_REQUIRED_GROUP}))"
        conn.search(search_base=AD_SEARCH_BASE, search_filter=search_filter, attributes=['sAMAccountName'])
        if len(conn.entries) > 0:
            return True, "Authentication successful."
        return False, "Access Denied."
    except Exception as e:
        return False, f"Authentication failed: {str(e)}"

# --- Modal (Pop-Up) Definition ---
@st.dialog("Data Explorer", width="large")
def open_course_modal(course_name, sync_date):
    
    if st.session_state.modal_view == 'roster':
        st.markdown(f"### 📘 Course Roster: {course_name}")
        st.info("👆 **Click the checkbox next to a student** to instantly pull up their full report card.")
        
        # Grab course_id to build the hyperlink
        query = f"SELECT student_name, current_score, current_grade, course_id FROM student_grades WHERE sync_timestamp = '{sync_date}' AND course_name = '{course_name}'"
        course_df = pd.read_sql(query, con=engine)
        
        # Build the dynamic URL column
        course_df['Course Page'] = "https://acalanes.instructure.com/courses/" + course_df['course_id'].astype(str)
        
        event = st.dataframe(
            course_df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "course_id": None, # Hide raw IDs
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
        
        # Fetch IDs for the student link generation
        query = f"""
            SELECT course_name, instructors, current_score, current_grade, 
                   last_access, missing_assignments, zeros, latest_submission, course_id, student_id
            FROM student_grades 
            WHERE sync_timestamp = '{sync_date}' AND student_name = '{student_name}'
        """
        student_df = pd.read_sql(query, con=engine)
        
        # Construct the Hyperlinks
        student_df['Course URL'] = "https://acalanes.instructure.com/courses/" + student_df['course_id'].astype(str)
        student_df['Grades URL'] = "https://acalanes.instructure.com/courses/" + student_df['course_id'].astype(str) + "/grades/" + student_df['student_id'].astype(str)
        student_df['Usage URL'] = "https://acalanes.instructure.com/courses/" + student_df['course_id'].astype(str) + "/users/" + student_df['student_id'].astype(str) + "/usage"

        student_df.rename(columns={
            'course_name': 'Course', 'instructors': 'Teacher', 'current_score': 'Score', 'current_grade': 'Grade',
            'last_access': 'Last Access', 'missing_assignments': 'Missing', 'zeros': 'Zeros', 'latest_submission': 'Latest Sub'
        }, inplace=True)
        
        # Order the columns nicely
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
# UI RENDERING LOGIC
# ==========================================

if not st.session_state.authenticated:
    st.subheader("🔒 Active Directory Login")
    with st.form("login_form"):
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        if st.form_submit_button("Log In"):
            if username_input and password_input:
                is_auth, msg = authenticate_user(username_input, password_input)
                if is_auth:
                    st.session_state.authenticated = True
                    st.session_state.username = username_input
                    st.rerun() 
                else:
                    st.error(msg)
            else:
                st.warning("Please enter both username and password.")
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
                    
                    # Fetch IDs for the student link generation
                    query_report = f"""
                        SELECT course_name, instructors, current_score, current_grade, 
                               last_access, missing_assignments, zeros, latest_submission, course_id, student_id
                        FROM student_grades 
                        WHERE sync_timestamp = '{selected_sync_student}' 
                        AND student_name = '{selected_student_search}'
                    """
                    report_df = pd.read_sql(query_report, con=engine)
                    
                    # Construct the Hyperlinks
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