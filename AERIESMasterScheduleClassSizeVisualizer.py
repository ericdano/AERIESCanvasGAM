import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path
import json
import math
import os
from timeit import default_timer as timer

"""
Master Schedule & Class Size Visualizer
Counselors and admin spend hours trying to balance class sizes at the start of the semester.

How it works: Pull data from the Master Schedule and Classes endpoints.

The Output: Python calculates the current enrollment for every section. 
We can use a library like matplotlib or pandas to generate a quick dashboard or spreadsheet
highlighting which teachers are overloaded and which sections have open seats.
This does need a different API endpoint than the one used for the student roster
 "AERIES_ADMIN_API_URL":"https://acalanes.aeries.net/admin/api/v5"

"""


# --- Global Configuration Placeholders ---
AERIES_URL = ""
API_KEY = ""
SCHOOL_CODES = ["1", "2", "3", "4"] 

def get_course_mapping(clean_base_url, headers):
    """Fetches course data from the district and creates a dictionary mapping CourseID to Course Name."""
    course_dict = {}
    endpoint = f"{clean_base_url}/courses"
    print("Fetching District Course Dictionary...")
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        courses = response.json()
        for course in courses:
            course_id = course.get('ID', course.get('CourseID'))
            course_name = course.get('Title', course.get('LongDescription', f"Course {course_id}"))
            
            if course_id:
                course_dict[str(course_id).strip()] = course_name.strip()
    else:
        print(f"Error {response.status_code} fetching courses: {response.text}")
            
    return course_dict

def get_multiple_master_schedules(clean_base_url, headers, school_codes):
    """Fetches the master schedule for multiple schools and combines them."""
    all_data = []
    
    for code in school_codes:
        endpoint = f"{clean_base_url}/schools/{code}/sections"
        print(f"Fetching Master Schedule for School {code}...")
        
        response = requests.get(endpoint, headers=headers)
        
        if response.status_code == 200:
            school_data = response.json()
            for record in school_data:
                record['SchoolCode'] = code
            all_data.extend(school_data)
        else:
            print(f"Error {response.status_code} for School {code}: {response.text}")
            
    return all_data

def generate_pdf_reports(data, course_dict):
    """Processes the data and creates a multi-page PDF for each school."""
    if not data:
        print("No data to visualize.")
        return

    df = pd.DataFrame(data)

    def get_teacher_name(staff_data):
        if isinstance(staff_data, list) and len(staff_data) > 0:
            first_teacher = staff_data[0]
            return first_teacher.get('Name', first_teacher.get('StaffName', 'Unknown Teacher'))
        return 'Unknown Teacher'

    df['TeacherName'] = df['SectionStaffMembers'].apply(get_teacher_name)

    df = df.rename(columns={
        'CourseID': 'CourseTitle', 
        'TotalStudents': 'TotalEnrolled',
        'MaxStudents': 'MaxSeats'
    })

    df['CourseTitle'] = df['CourseTitle'].astype(str).str.strip()
    df['CourseTitle'] = df['CourseTitle'].map(course_dict).fillna(df['CourseTitle'])

    df['UniqueCourseLabel'] = df['CourseTitle'] + " (Sec: " + df['SectionNumber'].astype(str) + ")"

    cols_to_keep = ['SchoolCode', 'TeacherName', 'UniqueCourseLabel', 'TotalEnrolled', 'MaxSeats']
    df = df[cols_to_keep]

    output_dir = Path.cwd() / "Aeries_Reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nSaving PDF reports to: {output_dir}")

    unique_schools = df['SchoolCode'].unique()
    
    for school in unique_schools:
        school_df = df[df['SchoolCode'] == school]
        school_sorted = school_df.sort_values(by='TotalEnrolled', ascending=False)
        
        pdf_filename = output_dir / f"School_{school}_Master_Schedule_Report.pdf"
        
        with PdfPages(pdf_filename) as pdf:
            classes_per_page = 25
            total_classes = len(school_sorted)
            num_pages = math.ceil(total_classes / classes_per_page)
            
            for page in range(num_pages):
                start_row = page * classes_per_page
                end_row = start_row + classes_per_page
                chunk = school_sorted.iloc[start_row:end_row]
                
                plt.figure(figsize=(11, 8.5)) 
                
                # --- CAPTURE THE CHART IN 'ax' ---
                ax = sns.barplot(
                    x='TotalEnrolled', 
                    y='UniqueCourseLabel', 
                    hue='TeacherName', 
                    data=chunk, 
                    dodge=False,
                    palette='viridis'
                )

                # --- NEW MAGIC: ADD NUMBERS TO THE BARS ---
                # Loop through the bars and add the text
                for container in ax.containers:
                    # padding=3 puts the number slightly past the end of the bar. 
                    # fmt='%.0f' ensures it prints as a whole number (no decimals).
                    ax.bar_label(container, fmt='%.0f', padding=3, fontweight='bold')
                # ------------------------------------------

                plt.title(f'Master Schedule Class Sizes - School {school} (Page {page + 1} of {num_pages})', fontsize=14, fontweight='bold')
                plt.xlabel('Number of Students Enrolled', fontsize=12)
                plt.ylabel('Course Title & Section', fontsize=12)
                
                plt.axvline(x=35, color='red', linestyle='--', label='Class Cap (35)')
                
                plt.legend(title='Teacher', bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small')
                plt.tight_layout()
                
                pdf.savefig()
                plt.close()
                
        print(f"✅ Generated PDF for School {school} ({num_pages} pages)")

# --- Main Execution ---
def main():
    global AERIES_URL, API_KEY

    start_of_timer = timer()
    
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    
    try:
        with open(confighome) as f:
            configs = json.load(f)
    except FileNotFoundError:
        print(f"Could not find the config file at {confighome}")
        return
        
    AERIES_URL = configs['AERIES_ADMIN_API_URL']
    API_KEY = configs['AERIES_API']
    
    headers = {
        "Aeries-Cert": API_KEY,
        "Content-Type": "application/json"
    }
    clean_base_url = AERIES_URL.rstrip('/')
    
    course_dictionary = get_course_mapping(clean_base_url, headers)
    combined_schedule_data = get_multiple_master_schedules(clean_base_url, headers, SCHOOL_CODES)
    
    generate_pdf_reports(combined_schedule_data, course_dictionary)
    
    end_of_timer = timer()
    print(f"\n🎉 Script completed in {end_of_timer - start_of_timer:.2f} seconds.")

if __name__ == "__main__":
    main()