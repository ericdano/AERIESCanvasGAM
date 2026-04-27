import os
from flask import Flask, request, render_template_string, session, redirect, url_for, flash
from ldap3 import Server, Connection, SIMPLE, ALL, SUBTREE, Tls
from ldap3.core.exceptions import LDAPBindError
from datetime import timedelta
import ftplib, ssl, sys, datetime, json, smtplib, logging
import sqlalchemy
from io import StringIO
from pathlib import Path
from ssl import SSLSocket
from timeit import default_timer as timer
import pandas as pd
import ldap3, pyodbc
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

# --- Flask App Initialization ---
app = Flask(__name__)
# IMPORTANT: Change this secret key in a production environment!
app.secret_key = os.environ.get('x1a_x01ox97xa8x86x9cxa8xc7x0bxa8Oxafx0bxf3bCfIBx9c', 'x96Tx14xe5xa2x02DRvx11-xe6xf8x86xef^PJxd1rBxda')

# --- LOAD CONFIGURATION (Moved up for Gunicorn compatibility) ---
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
try:
    with open(confighome) as f:
        configs = json.load(f)
    print(f"Successfully loaded config from {confighome}", flush=True)
except FileNotFoundError:
    print(f"CRITICAL ERROR: Could not find config file at {confighome}", flush=True)
    configs = {}
except Exception as e:
    print(f"Error reading config: {e}", flush=True)
    configs = {}

# --- Active Directory Configuration ---
AD_SERVER = "10.99.0.44"
AD_PORT = 636
AD_USE_SSL = True
AD_DOMAIN_NAME = "acalanes.k12.ca.us"
AD_SEARCH_BASE = "DC=acalanes,DC=k12,DC=ca,DC=us"
AD_SEARCH_BASE2 = "DC=staff,DC=acalanes,DC=k12,DC=ca,DC=us"
AD_REQUIRED_GROUP_DN = "CN=Aeries2FA,CN=Users,DC=acalanes,DC=k12,DC=ca,DC=us"
