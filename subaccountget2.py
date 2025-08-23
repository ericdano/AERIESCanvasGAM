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
Python Script to get all Account Roles

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
    # Miramonte HS is Subaccount 147
    print(f"{term_id}")
    subaccount = canvas.get_account(147)
    all_academy_teacher_enrollments = []
    print('try')
    try:
        all_courses = subaccount.get_courses(enrollment_type=['teacher'], enrollment_term_id=term_id)
        print('try2')
        for course in all_courses:
            academy_teacher_enrollments = course.get_enrollments(role=["Academy Teachers"])
            print(f"{academy_teacher_enrollments.label}")
            """
            for enrollment in academy_teacher_enrollments:
                all_academy_teacher_enrollments.append({
                    "user_id": enrollment.user_id,
                    "user_name": enrollment.user["name"],
                    "course_id": enrollment.course_id,
                    "course_name": course.name,
                })
            """
    except Exception as e:
        print(f"An error occurred: {e}")
    #print(all_academy_teacher_enrollments)
if __name__ == '__main__':
    main()