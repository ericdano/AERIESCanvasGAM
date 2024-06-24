import pandas as pd
import requests, json, logging, smtplib, datetime, sys
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage

#
# This program enrols a CSV list of users into a Canvas Group
# Usage is >python CSV_To_Group.py groupid csvname.csv
#More of a TEST PROGRAM than something that is usable

#load configs
home = Path.home() / ".Acalanes" / "Acalanes.json"
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
Canvas_API_URL = configs['CanvasBETAAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']
canvas = Canvas(Canvas_API_URL, Canvas_API_KEY)
account = canvas.get_account(1)
course = canvas.get_course(12959)
#get main course
'''
users = course.get_users()
for user in users:
    print(user)
'''
print('---------Sections----------------')
sections = course.get_sections()
for idx,section in enumerate(sections):
    print(section)
    print(section.id)
    print(idx)
print('---------Sections----------------')
'''
thesection = sections[0]
new_section = sections[0].cross_list_section('12959') #this is where all the course are going to be cross listed to
'''