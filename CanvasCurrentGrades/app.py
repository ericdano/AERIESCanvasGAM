import os
import json
import pandas as pd
import streamlit as st
from datetime import datetime
from canvasapi import Canvas
from sqlalchemy import create_engine, inspect
from pathlib import Path

# --- Setup UI ---
st.set_page_config(page_title="Canvas Grade Extractor", layout="wide")
st.title("Canvas Account-Level Grade Extractor")

# --- Load Configuration ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"

try:
    with open(confighome, 'r') as f:
        configs = json.load(f)
        
    API_URL = configs.get('CanvasAPIURL')
    API_KEY = configs.get('CanvasAPIKey')
    ACCOUNT_ID = configs.get('CanvasAccountID', 1) 
    TARGET_TERM_IDS = configs.get('TargetTermIDs')
    
    if not API_URL or not API_KEY:
        st.error(f"Missing 'CanvasAPIURL' or 'CanvasAPIKey' in {confighome}")
        st.stop()
        
    if not TARGET_TERM_IDS or not isinstance(TARGET_TERM_IDS, list):
        st.error("Missing or invalid 'TargetTermIDs'. It must be a list of integers (e.g., [123, 124]).")
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
# We keep the engine around ONLY for the SQLAlchemy inspector tool
engine = create_engine(db_url)

# --- Helper Function: Check for existing syncs ---
def get_sync_dates():
    inspector = inspect(engine)
    if 'student_grades' in inspector.get_table_names():
        query = "SELECT DISTINCT sync_timestamp FROM student_grades ORDER BY sync_timestamp DESC"
        try:
            # FIX: Pass db_url directly to Pandas
            df_dates = pd.read_sql(query, con=db_url)
            return df_dates['sync_timestamp'].tolist()
        except Exception:
            return []
    return []

existing_syncs = get_sync_dates()

# --- Sidebar Configuration ---
st.sidebar.header("Data Sync Setup")
st.sidebar.success("✅ Connected via config.json")
# Display the currently loaded config variables to the user
st.sidebar.info(f"**Account ID:** {ACCOUNT_ID}\n\n**Term IDs:** {', '.join(map(str, TARGET_TERM_IDS))}")

# --- Sync Logic Function ---
def run_canvas_sync():
    canvas = Canvas(API_URL, API_KEY)
    sync_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        account = canvas.get_account(ACCOUNT_ID)
        all_grades_data = []
        
        progress_text = st.empty()
        progress_bar = st.progress(0)

        for idx, term_id in enumerate(TARGET_TERM_IDS):
            progress_text.text(f"Fetching courses for Term ID: {term_id}...")
            courses = account.get_courses(enrollment_term_id=term_id, state=['available'], include=['teachers'])
            
            for course in courses:
                try:
                    teacher_names = [t.get('display_name', 'Unknown') for t in getattr(course, 'teachers', [])]
                    instructor_string = ", ".join(teacher_names) if teacher_names else "No Instructor"
                    
                    users = course.get_users(enrollment_type=['student'], include=['enrollments'])
                    
                    for user in users:
                        if hasattr(user, 'enrollments'):
                            for enrollment in user.enrollments:
                                grades = enrollment.get('grades', {})
                                all_grades_data.append({
                                    'sync_timestamp': sync_timestamp,
                                    'term_id': term_id,
                                    'course_id': course.id,
                                    'course_name': course.name,
                                    'instructors': instructor_string,
                                    'student_name': user.name,
                                    'current_score': grades.get('current_score'),
                                    'current_grade': grades.get('current_grade')
                                })
                except Exception:
                    pass 
            
            progress_bar.progress((idx + 1) / len(TARGET_TERM_IDS))

        progress_text.text("Extraction complete. Pushing to database...")

        if all_grades_data:
            df = pd.DataFrame(all_grades_data)
            
            # FIX: Pass db_url directly to Pandas instead of managing a connection
            df.to_sql(name='student_grades', con=db_url, if_exists='append', index=False)
                
            st.success(f"Successfully synced {len(df)} records at {sync_timestamp}!")
            st.rerun() 
        else:
            st.info("No data found for the provided Term IDs.")

    except Exception as e:
        st.error(f"Canvas API Error: {e}")

# --- Main UI Rendering ---

if not existing_syncs:
    st.warning("The database is currently empty. No historical grade data found.")
    st.markdown("Please verify your config variables in the sidebar and run the initial sync.")
    if st.button("Run Initial Data Sync", type="primary"):
        run_canvas_sync()

else:
    if st.sidebar.button("Run New Sync Now", type="primary"):
        run_canvas_sync()

    tab1, tab2 = st.tabs(["🗄️ Data Viewer", "📈 Analytics & Trends"])
    
    with tab1:
        st.subheader("Historical Grade Viewer")
        selected_sync = st.selectbox(
            "Select a Data Sync Date to View:", 
            options=existing_syncs,
            index=0 
        )
        
        if selected_sync:
            query = f"SELECT * FROM student_grades WHERE sync_timestamp = '{selected_sync}'"
            
            # FIX: Pass db_url directly to Pandas
            historical_df = pd.read_sql(query, con=db_url)
            st.write(f"Showing **{len(historical_df)}** records from the sync on: **{selected_sync}**")
            st.info("👆 **Click the checkbox on the far-left edge of any row** to automatically pull that Course's Roster and that Student's Report Card.")
            
            # The Interactive Dataframe
            event = st.dataframe(
                historical_df, 
                use_container_width=True,
                on_select="rerun", 
                selection_mode="single-row",
                hide_index=False # Forces the clickable checkbox column to remain visible
            )
            
            # Use Streamlit's official attribute-based access for selections
            selected_rows = event.selection.rows
            
            if selected_rows:
                row_idx = selected_rows[0]
                selected_course = historical_df.iloc[row_idx]['course_name']
                selected_student = historical_df.iloc[row_idx]['student_name']
                
                st.divider()
                st.subheader("🔍 Instant Drill-Down")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Course Roster: {selected_course}**")
                    course_df = historical_df[historical_df['course_name'] == selected_course]
                    st.dataframe(
                        course_df[['student_name', 'current_score', 'current_grade']].reset_index(drop=True), 
                        use_container_width=True
                    )
                    
                with col2:
                    st.markdown(f"**Report Card: {selected_student}**")
                    student_df = historical_df[historical_df['student_name'] == selected_student]
                    st.dataframe(
                        student_df[['course_name', 'instructors', 'current_score', 'current_grade']].reset_index(drop=True), 
                        use_container_width=True
                    )

    with tab2:
        st.subheader("Average Score Trends Over Time")
        st.markdown("Track how the average scores across your selected terms change with each sync.")

        all_data_query = "SELECT sync_timestamp, current_score FROM student_grades"
        
        # FIX: Pass db_url directly to Pandas
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