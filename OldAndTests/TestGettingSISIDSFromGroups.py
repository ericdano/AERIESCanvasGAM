import pandas as pd
import os, sys, shlex, subprocess, json
from pathlib import Path
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
  configs = json.load(f)
# Logging
#-----Canvas Info
Canvas_API_URL = configs['CanvasAPIURL']
Canvas_API_KEY = configs['CanvasAPIKey']


#Set up Counselors to pull from Aeries along with the Canvas groups they are part of
counselors = [ ('acis','feinberg',10831)]


canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
group = canvas.get_group(10831,include=['users'])
dataframe2 = pd.DataFrame(group.users,columns=['login_id','sis_user_id'])
pd.set_option('display.max_rows',dataframe2.shape[0]+1)
print(dataframe2)
user=canvas.get_user(1011580)
print(user)