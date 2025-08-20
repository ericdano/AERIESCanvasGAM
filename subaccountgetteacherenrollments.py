import pandas as pd
import os, sys, shlex, subprocess, datetime, json, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

""" 
Python Script to get all Teachger Enrollments in a Subaccount for a given Term 

2025 by Eric Dannewitz
"""

def main():
    start_of_timer = timer()
    WasThereAnError = False  
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    if configs['logserveraddress'] is None:
        logfilename = Path.home() / ".Acalanes" / configs['logfilename']
        thelogger = logging.getLogger('MyLogger')
        thelogger.basicConfig(filename=str(logfilename), level=thelogger.info)
    else:
        thelogger = logging.getLogger('MyLogger')
        thelogger.setLevel(logging.DEBUG)
        handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
        thelogger.addHandler(handler)
    Canvas_API_URL = configs['CanvasAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']  
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    # Need the main account to as we have to FIND the Term
    # This is in case multiple subaccounts want to do the same sort of thing
    account = canvas.get_account(1)

    # Miramonte HS is Subaccount 147
    subaccount = canvas.get_account(147)
    
    try:
        # First FIND the Enrollment Term ID based on the Name
        term_name= '2025/2026 - Miramonte High School - Year'
        terms = account.get_enrollment_terms()
        term_id = 0
        print(f"Looking for {term_name} in Canvas")
        for term in terms:
            print(f"{term.name} ({term.id})")
            if term.name == term_name:
                logging.info('Found Term ID')
                term_id = term.id
            else:
                logging.info('Looking for Term ID')
                print('Looking for Term ID')
        if term_id == 0:
            print('Term ID is still 0, stopping program.')
            #dmsgbody=dmsgbody+'Did not find Term in Canvas. Aborted program.'
        else:
            print(term_id)
            # Get all courses within the subaccount.
            # We include 'enrollment_type' to filter for courses that have at least one teacher enrollment.
            courses = subaccount.get_courses(enrollment_type=['teacher'], enrollment_term_id=term_id)

            teacher_enrollments = []

            # Loop through each course to get teacher enrollments
            for course in courses:
                print(f"Searching course: {course.name} ({course.id})")
                # Get enrollments for the course, filtering specifically for TeacherEnrollment
                enrollments = course.get_enrollments(type=['TeacherEnrollment'])
                
                # Extend the list with the found enrollments
                teacher_enrollments.extend(enrollments)

            # Print the results
            print("\nFound Teacher Enrollments:")
            for enrollment in teacher_enrollments:
                print(f"Teacher: {enrollment.user['name']} (ID: {enrollment.user_id}) - Course ID: {enrollment.course_id}")

    except Exception as e:
        print(f"An error occurred: {e}")
if __name__ == '__main__':
    main()