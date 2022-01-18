import pandas as pd
import os, sys, pyodbc, shlex, subprocess, json
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


canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
account = canvas.get_account(1)
#group = canvas.get_group(10831,include=['users'])
#df = pd.DataFrame(group.users,columns=['id','name','login_id'])
