from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
import json

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)

Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
user = canvas.get_user(141)
course = canvas.get_course(9295)
course.enroll_user(
    user,
    enrollment_type = "StudentEnrollment",
    enrollment={
        'course_section_id': 10041,
        'enrollment_state': 'active'
    }
)
course.enroll_user(
    user,
    enrollment_type = "StudentEnrollment",
    enrollment={
        'course_section_id': 10037,
        'enrollment_state': 'active'
    }
)
course.enroll_user(
    user,
    enrollment_type = "StudentEnrollment",
    enrollment={
        'course_section_id': 10038,
        'enrollment_state': 'active'
    }
)