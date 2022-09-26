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
    enrollment={'enrollment_state': 'active'}
)
enrollments = course.get_enrollments(type='StudentEnrollment')
for stu in enrollments:
    if stu.user_id == user.id:
        print('Found ->' + str(stu.id) + ' ' + str(stu.type) + ' ' + str(stu.user_id) + ' ' + str(stu.course_section_id))
        print(vars(stu))
#            lookfordelete = False
#            for stu in enrollments:
#                # You have to loop through all the enrollments for the class and then find the student id in the enrollment then tell it to delete it.
#                if stu.user_id == user.id:
#                    lookfordelete = True
#                    stu.deactivate(task='delete')
print('Done')