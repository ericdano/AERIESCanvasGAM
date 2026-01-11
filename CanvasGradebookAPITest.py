import requests
import os
import json
from pathlib import Path

# --- Configuration ---
# IMPORTANT: Replace these placeholders with your actual credentials and IDs.
# It is highly recommended to load these from environment variables for security.

# Canvas API Base URL (e.g., 'https://yourinstitution.instructure.com')
CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "https://acalanes.instructure.com")
# Your Canvas Personal Access Token (API Key)
#CANVAS_API_KEY = os.environ.get("CANVAS_API_KEY", "YOUR_CANVAS_API_KEY")

# IDs for the specific grade you want to retrieve
COURSE_ID = 11584            # Replace with the numerical ID of the course
ASSIGNMENT_ID = 789012        # Replace with the numerical ID of the assignment
STUDENT_ID = 345678           # Replace with the numerical ID of the student

# --- API Interaction ---

def get_student_assignment_grade(base_url, api_key, course_id, assignment_id, student_id):
    """
    Retrieves the submission details, including the grade, for a specific student 
    and assignment using the Canvas Submissions API.

    Args:
        base_url (str): The base URL of your Canvas instance.
        api_key (str): Your Canvas personal access token.
        course_id (int): The ID of the course.
        assignment_id (int): The ID of the assignment.
        student_id (int): The ID of the student.

    Returns:
        dict or None: The submission JSON data, or None if an error occurred.
    """
    
    # 1. Define the API endpoint URL for a specific submission
    # The Submissions API is the standard way to get a grade for a single assignment.
    # Endpoint: /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id
    url = f"{base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{student_id}"

    # 2. Set up headers for authorization
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    # 3. Define parameters to ensure we get the necessary grade information
    params = {
        # 'include[]': 'submission_history' # Use this if you want all submission attempts/history
        'include[]': 'assignment' # Includes assignment metadata (like points possible)
    }

    print(f"Attempting to fetch grade for Student {student_id} on Assignment {assignment_id}...")

    try:
        # 4. Make the GET request to the Canvas API
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        submission_data = response.json()

        # 5. Extract and display the relevant grade information
        
        score = submission_data.get('score')
        points_possible = submission_data.get('assignment', {}).get('points_possible')
        
        print("\n--- Grade Retrieved Successfully ---")
        print(f"Student ID: {student_id}")
        print(f"Assignment Title: {submission_data.get('assignment', {}).get('name', 'N/A')}")
        print(f"Current Score: {score}")

        if score is not None and points_possible is not None:
            if points_possible > 0:
                percentage = (score / points_possible) * 100
                print(f"Percentage: {percentage:.2f}%")
            else:
                print("Points Possible: 0 (Cannot calculate percentage)")

        print(f"Current Grade (Letter/Status): {submission_data.get('grade', 'N/A')}")
        print(f"Submission Workflow State: {submission_data.get('workflow_state')}")
        print("------------------------------------")
        
        return submission_data

    except requests.exceptions.HTTPError as e:
        print(f"\nError: Failed to retrieve grade. HTTP Status Code: {e.response.status_code}")
        # Try to parse Canvas specific error messages
        try:
            error_details = e.response.json()
            print(f"Canvas Error Details: {json.dumps(error_details, indent=4)}")
        except json.JSONDecodeError:
            print("Canvas Error Details: Could not decode error response.")
        
        print(f"Check if the COURSE_ID, ASSIGNMENT_ID, and STUDENT_ID are correct.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"\nAn unexpected request error occurred: {e}")
        return None

# --- Main Execution Block ---

if __name__ == "__main__":
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    CANVAS_API_KEY = configs['CanvasAPIURL']

    # Run the retrieval function
    grade_info = get_student_assignment_grade(
        CANVAS_BASE_URL, 
        CANVAS_API_KEY, 
        COURSE_ID, 
        ASSIGNMENT_ID, 
        STUDENT_ID
    )

    # Optional: Save the full submission details to a file
    if grade_info:
        filename = f"submission_data_{STUDENT_ID}_{ASSIGNMENT_ID}.json"
        with open(filename, 'w') as f:
            json.dump(grade_info, f, indent=4)
        print(f"\nFull submission data saved to {filename}")