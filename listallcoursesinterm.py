from sqlalchemy.engine import URL
from sqlalchemy import create_engine
import pandas as pd
from pathlib import Path
from timeit import default_timer as timer
import requests, json, logging, smtplib, datetime, sys
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException, ResourceDoesNotExist
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
import time

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
    configs = json.load(f)
# 1. Setup credentials
API_URL = configs['CanvasAPIURL']
API_KEY = configs['CanvasAPIKey']
canvas = Canvas(API_URL, API_KEY)

TARGET_TERM_ID = 425

# Connect to Canvas
canvas = Canvas(API_URL, API_KEY)
account = canvas.get_account(1) 

# ==========================================
# 2. FETCH AND LIST COURSE IDS
# ==========================================
print(f"Fetching all courses in term ID {TARGET_TERM_ID}...")

# The state array ensures we don't miss courses based on their publish status
term_courses = account.get_courses(
    enrollment_term_id=TARGET_TERM_ID,
    state=['created', 'claimed', 'available', 'completed']
)

# Store the IDs in a list
course_ids = []

for course in term_courses:
    course_ids.append(course.id)
    # Optional: Print them out one by one as it finds them
    print(f"ID: {course.id} | Name: {course.name}")

# Print the final count and the raw list of IDs
print("\n--- SUMMARY ---")
print(f"Total courses found: {len(course_ids)}")
print("\nRaw Python List of IDs (Easy to copy/paste):")
print(course_ids)