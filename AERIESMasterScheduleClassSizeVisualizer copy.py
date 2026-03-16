import requests
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import json
from timeit import default_timer as timer

# --- Global Configuration Placeholders ---
AERIES_URL = ""
API_KEY = ""
SCHOOL_CODES = ["1", "2", "3", "4"] 

def get_course_mapping(clean_base_url, headers):
    """Fetches course data from the district and creates a dictionary mapping CourseID to Course Name."""
    course_dict = {}
    
    # THE FIX: Courses are district-wide, not school-specific!
    endpoint = f"{clean_base_url}/courses"
    print(f"DEBUG: Fetching District Course Dictionary from -> {endpoint}")
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        courses = response.json()
        for course in courses:
            # Aeries uses 'ID' for the course number in this endpoint
            course_id = course.get('ID', course.get('CourseID'))
            # They use 'Name' for the readable title
            course_name = course.get('Name', course.get('LongName', f"Course {course_id}"))
            
            if course_id:
                # Strip whitespace just in case Aeries has hidden spaces in the ID
                course_dict[str(course_id).strip()] = course_name.strip()
    else:
        print(f"Error {response.status_code} fetching courses: {response.text}")
            
    return course_dict

def get_multiple_master_schedules(clean_base_url, headers, school_codes):
    """Fetches the master schedule for multiple schools and combines them."""
    all_data = []
    
    for code in school_codes:
        endpoint = f"{clean_base_url}/schools/{code}/sections"
        print(f"DEBUG: Fetching Master Schedule for School {code}...")
        
        response = requests.get(endpoint, headers=headers)
        
        if response.status_code == 200:
            school_data = response.json()
            
            # Inject the school code into every row so we can filter it later
            for record in school_data:
                record['SchoolCode'] = code
                
            # Add this school's data to our master list
            all_data.extend(school_data)
        else:
            print(f"Error {response.status_code} for School {code}: {response.text}")
            
    return all_data

def visualize_multiple_schools(data, course_dict):
    """Processes the combined JSON data, maps course names, and creates charts."""
    if not data:
        print("No data to visualize. Check your API connection or school codes.")
        return

    df = pd.DataFrame(data)

    # 1. Safely extract the Teacher's Name
    def get_teacher_name(staff_data):
        if isinstance(staff_data, list) and len(staff_data) > 0:
            first_teacher = staff_data[0]
            return first_teacher.get('Name', first_teacher.get('StaffName', 'Unknown Teacher'))
        return 'Unknown Teacher'

    df['TeacherName'] = df['SectionStaffMembers'].apply(get_teacher_name)

    # 2. Rename columns based on our previous discovery
    df = df.rename(columns={
        'CourseID': 'CourseTitle', 
        'TotalStudents': 'TotalEnrolled',
        'MaxStudents': 'MaxSeats'
    })

    # 3. USE OUR DICTIONARY TO TRANSLATE COURSE IDs TO NAMES
    df['CourseTitle'] = df['CourseTitle'].astype(str).str.strip()
    # Look up the ID in our dictionary and swap it for the name
    df['CourseTitle'] = df['CourseTitle'].map(course_dict).fillna(df['CourseTitle'])

    # 4. Filter columns down to just what we need
    cols_to_keep = ['SchoolCode', 'TeacherName', 'CourseTitle', 'SectionNumber', 'TotalEnrolled', 'MaxSeats']
    df = df[cols_to_keep]

    # 5. Create a new column to see how many seats are left
    df['SeatsAvailable'] = df['MaxSeats'] - df['TotalEnrolled']

    # 6. Generate a separate chart for each school
    unique_schools = df['SchoolCode'].unique()
    
    for school in unique_schools:
        school_df = df[df['SchoolCode'] == school]
        
        # Sort the data so the fullest classes are at the top (Top 15)
        school_sorted = school_df.sort_values(by='TotalEnrolled', ascending=False).head(15) 
        
        plt.figure(figsize=(10, 6))
        
        sns.barplot(
            x='TotalEnrolled', 
            y='CourseTitle', 
            hue='TeacherName', 
            data=school_sorted, 
            dodge=False,
            palette='viridis'
        )

        plt.title(f'Top 15 Largest Classes - School {school}', fontsize=14, fontweight='bold')
        plt.xlabel('Number of Students Enrolled', fontsize=12)
        plt.ylabel('Course Title', fontsize=12)
        
        plt.axvline(x=35, color='red', linestyle='--', label='Class Cap (35)')
        
        # Move legend outside the chart
        plt.legend(title='Teacher', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        
        plt.show()

# --- Main Execution ---
def main():
    global AERIES_URL, API_KEY

    start_of_timer = timer()
    
    # Load configuration from JSON file
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
    
    # 1. Fetch the Dictionary of Course Names (Notice we don't pass SCHOOL_CODES anymore!)
    course_dictionary = get_course_mapping(clean_base_url, headers)
    
    # 2. Fetch the Master Schedule Data
    combined_schedule_data = get_multiple_master_schedules(clean_base_url, headers, SCHOOL_CODES)
    
    # 3. Combine them and Visualize!
    visualize_multiple_schools(combined_schedule_data, course_dictionary)
    
    end_of_timer = timer()
    print(f"Script completed in {end_of_timer - start_of_timer:.2f} seconds.")

if __name__ == "__main__":
    main()