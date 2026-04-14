import os
import ssl 
import json
import pandas as pd
import streamlit as st
from datetime import datetime
from sqlalchemy import create_engine, inspect
from pathlib import Path
from ldap3 import Server, Connection, ALL, Tls

# --- Setup UI ---
st.set_page_config(page_title="Canvas Grade Extractor", layout="wide")
st.title("Canvas Account-Level Grade Extractor")

# --- Initialize Session State for Authentication ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None

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
db_url = os.getenv("DATABASE_URL", "mysql+pymysql://canvas_user:canvas_password@db:3306/canvas_data")
engine = create_engine(db_url)

# --- Helper Function: Check for existing syncs ---
def get_sync_dates():
    inspector = inspect(engine)
    if 'student_grades' in inspector.get_table_names():
        query = "SELECT DISTINCT sync_timestamp FROM student_grades ORDER BY sync_timestamp DESC"
        try:
            df_dates = pd.read_sql(query, con=db_url)
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
    st.sidebar.header("Dashboard Controls")
    st.sidebar.success(f"✅ Logged in as: {st.session_state.username}")
    
    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
        
    st.sidebar.divider()

    if not existing_syncs:
        st.info("The database is currently empty. The automated background sync is scheduled to run at 6:30 AM.")
        st.markdown("Please check back after the sync completes.")
    else:
        # --- Sidebar Filters ---
        selected_sync = st.sidebar.selectbox(
            "Select Data Sync Date:", 
            options=existing_syncs,
            index=0 
        )
        
        view_mode = st.sidebar.radio(
            "Explore Data By:", 
            options=["Course", "Student"]
        )

        tab1, tab2 = st.tabs(["🗄️ Interactive Data Explorer", "📈 Analytics & Trends"])
        
        with tab1:
            if selected_sync:
                query = f"SELECT * FROM student_grades WHERE sync_timestamp = '{selected_sync}'"
                historical_df = pd.read_sql(query, con=db_url)
                
                if view_mode == "Student":
                    st.subheader("🧑‍🎓 Step 1: Select a Student")
                    st.info("👆 Click the checkbox next to a student to view their report card.")
                    
                    # Create a dataframe of unique student names
                    unique_students = historical_df[['student_name']].drop_duplicates().sort_values('student_name').reset_index(drop=True)
                    
                    event_top = st.dataframe(
                        unique_students, 
                        use_container_width=True,
                        on_select="rerun", 
                        selection_mode="single-row",
                        hide_index=False
                    )
                    
                    if event_top.selection.rows:
                        selected_student = unique_students.iloc[event_top.selection.rows[0]]['student_name']
                        
                        st.divider()
                        st.subheader(f"📊 Step 2: Report Card for {selected_student}")
                        
                        # Filter to show only that student's grades
                        student_df = historical_df[historical_df['student_name'] == selected_student]
                        st.dataframe(
                            student_df[['course_name', 'instructors', 'current_score', 'current_grade']].reset_index(drop=True), 
                            use_container_width=True
                        )

                elif view_mode == "Course":
                    st.subheader("🏫 Step 1: Select a Course")
                    st.info("👆 Click the checkbox next to a course to view its roster and grades.")
                    
                    # Create a dataframe of unique course names
                    unique_courses = historical_df[['course_name']].drop_duplicates().sort_values('course_name').reset_index(drop=True)
                    
                    event_top = st.dataframe(
                        unique_courses, 
                        use_container_width=True,
                        on_select="rerun", 
                        selection_mode="single-row",
                        hide_index=False
                    )
                    
                    if event_top.selection.rows:
                        selected_course = unique_courses.iloc[event_top.selection.rows[0]]['course_name']
                        
                        st.divider()
                        st.subheader(f"📋 Step 2: Roster for {selected_course}")
                        st.info("👆 Click the checkbox next to any student below to pull up their full cross-course report card.")
                        
                        # Filter to show only the students in that course
                        course_df = historical_df[historical_df['course_name'] == selected_course][['student_name', 'current_score', 'current_grade']].reset_index(drop=True)
                        
                        event_bottom = st.dataframe(
                            course_df, 
                            use_container_width=True,
                            on_select="rerun", 
                            selection_mode="single-row",
                            hide_index=False
                        )
                        
                        # THE DEEP DIVE WINDOW
                        if event_bottom.selection.rows:
                            selected_student_deep = course_df.iloc[event_bottom.selection.rows[0]]['student_name']
                            
                            st.divider()
                            st.subheader(f"🗂️ Step 3: Deep Dive - {selected_student_deep}'s Full Report Card")
                            
                            # Filter to show the clicked student's grades across ALL their courses
                            deep_student_df = historical_df[historical_df['student_name'] == selected_student_deep]
                            st.dataframe(
                                deep_student_df[['course_name', 'instructors', 'current_score', 'current_grade']].reset_index(drop=True), 
                                use_container_width=True
                            )

        with tab2:
            st.subheader("Average Score Trends Over Time")
            st.markdown("Track how the average scores across your selected terms change with each sync.")

            all_data_query = "SELECT sync_timestamp, current_score FROM student_grades"
            trend_df = pd.read_sql(all_data_query, con=db_url)

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