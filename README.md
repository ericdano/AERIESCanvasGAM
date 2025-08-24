# AERIESCanvasGAM

Python scripts/programs to do things with AERIES SIS, Canvas LMS, and Google (using GAM)

GuestUsers.py - A program I wrote during COVID lockdown that randomly generates weekly new passwords for a set of Guest Accounts we were using for Zoom.

SuspendUsers.py - A linux run script that goes through all the suspended users, puts them in a "Former Staff" OU and takes them out of Google Groups

DisableStudentVacationResponder.py - Weekly run thing to turn off students who think it's funny to put on the vacation responder

StudentAddPagerFromlogonname.ps1 - Powershell Script to go through active directory, and put student's SIS ID into the Pager field. Used by Papercut

CanvasGroups_ACISCounselingToCanvas.py - Takes an AERIES database query of what students the Independent Study Counselor has and updates the Canvas Group

CanvasGroups_CounselorsToCanvasGroup.py - Takes an AERIES database query of multiple Counselors and updates their Canvas Group
*Note* this does work, but the functionality of Canvas groups changed in 2023, and you can no longer email EVERYONE in the group. This script now
does the same thing but for a "Class" for each counselor, and each grade is a Section of the main course.

CanvasGroups_GoogleSheetToGroup.py - Takes a master list of a teacher email, Google Sheet ID, Canvas Group ID and updates a Canvas Group based on Emails contained in the Google Sheet ID. Used for making Groups in Canvas for like Librarians who want to message in Canvas to students who might have fines, etc.
*Note* this does work, but the functionality of Canvas groups changed in 2023, and you can no longer email EVERYONE in the group. Dumb. 
This script hasn't been updated cause no one was using it. Probably needs to be redone to be like the Counselor one.

AllCampusStudentInformationCourses.py - Is a script that takes data from AERIES and then puts students in an informational course, and a corresponding section of that course for their grade. It is used for campus wide announcements and stuff.

ExpireADAccounts.py - Set an expiration date in AD, and this script will then, when it finds accounts with that date, disable AD/Google/Canvas accounts for the users/

AERIES Canvas Course Renamer and Crosslister - One of the issues we have with the current AERIES to Canvas sync is that the naming of the classes suck. And a lot of classes need to be hand cross-listed. This script solves that issue, and will rename a class with the School year (24-25) Course Name - LastName Period format.

UpdateGoogleStaffInfo.ps1 - We use Active Directory, so all the staff info is in there. This powershell script makes a csv of staff data, and the GAM is used to update the stuff in Google

UpddateGoogleStudentGroupsFromAERIES.py - Looks in AERIES SIS, gets all the students from 5 sites, makes CSV files by Site and Grade, and then updates Google Groups with GAM that are based off the CSV file name
So, ahsgrade9students list is updated from the ahsgrade9students.csv file.

DisableADAccountsinAD.ps1 - goes through a CSV and disables accounts.

CreateNewStudents2025.ps1 - Powershell script to create Students in the correct OU, with the correct groups, and create the correct H:\ drive path for the account

fixstudentdirectoryownership.ps1 - To fix an issue with CreateNewStudents2025 being so fast, permissions we not being correctly set because the NAS did not have enough time to receive the information from the
AD Server that a new user was created. This will SHOULD be run right after CreateNewStudents2025