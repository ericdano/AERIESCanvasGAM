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


# --- HTML Templates ---
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AUHSD 2FA Reset</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 flex items-center justify-center h-screen">
    <div class="w-full max-w-md">
        <form class="bg-white shadow-lg rounded-xl px-8 pt-6 pb-8 mb-4" method="post" action="{{ url_for('login') }}">
            <h1 class="text-2xl font-bold text-center text-gray-800 mb-6">AERIES 2FA Reset Login</h1>

            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="mb-4 px-4 py-3 rounded-lg relative {{ 'bg-red-100 border border-red-400 text-red-700' if category == 'error' else 'bg-blue-100 border border-blue-400 text-blue-700' }}" role="alert">
                    <span class="block sm:inline">{{ message }}</span>
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}
            <div class="mb-4">
                <label class="block text-gray-700 text-sm font-bold mb-2" for="domain">
                    Domain
                </label>
                <input class="shadow-sm appearance-none border rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-500" id="domain" name="domain" type="text" placeholder="domain" required>
            </div>
            <div class="mb-5">
                <label class="block text-gray-700 text-sm font-bold mb-2" for="username">
                    Username
                </label>
                <input class="shadow-sm appearance-none border rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-500" id="username" name="username" type="text" placeholder="username" required>
            </div>

            <div class="mb-6">
                <label class="block text-gray-700 text-sm font-bold mb-2" for="password">
                    Password
                </label>
                <input class="shadow-sm appearance-none border rounded-lg w-full py-3 px-4 text-gray-700 mb-3 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-500" id="password" name="password" type="password" placeholder="******************" required>
            </div>
            <div class="flex items-center justify-between">
                <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg focus:outline-none focus:shadow-outline w-full" type="submit">
                    Sign In
                </button>
            </div>
        </form>
        <p class="text-center text-gray-500 text-xs">
            &copy;2025 Acalanes Union High School District. All rights reserved.
        </p>
    </div>
</body>
</html>
"""

HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <nav class="bg-white shadow-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex items-center justify-between h-16">
                <div class="flex-shrink-0 text-xl font-bold text-gray-800">
                    AERIES 2FA Reset Page
                </div>
                <div class="flex items-center">
                    <p class="text-gray-700 mr-4">Welcome, <span class="font-semibold">{{ session['username'] }}</span>!</p>
                    <a href="{{ url_for('logout') }}" class="bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded-lg focus:outline-none focus:shadow-outline">
                        Logout
                    </a>
                </div>
            </div>
        </div>
    </nav>
    <main class="mt-10">
        <div class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
            <div class="px-4 py-6 sm:px-0 bg-white rounded-xl shadow-lg">
                <div class="border-4 border-dashed border-gray-200 rounded-lg h-96 p-8 text-center">
                    <h2 class="text-3xl font-bold text-gray-800">Authentication Successful</h2>
                    <p class="mt-4 text-gray-600">Please enter the domain of the user, and the users login</p>
                    <p class="mt-4 text-gray-600">Example-> Domain -> staff Login -> jdoe</p>
                    <p class="mt-4 text-gray-600">YOUR SESSION WILL EXPIRE IN 60 SECONDS or Upon SUBMITTING the form</p>

            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="mb-4 px-4 py-3 rounded-lg relative {{ 'bg-red-100 border border-red-400 text-red-700' if category == 'error' else 'bg-blue-100 border border-blue-400 text-blue-700' }}" role="alert">
                    <span class="block sm:inline">{{ message }}</span>
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}
                </div>
                <form class="bg-white shadow-lg rounded-xl px-8 pt-6 pb-8 mb-4" method="post" action="{{ url_for('resetaeries2fa') }}">
                    <h1 class="text-2xl font-bold text-center text-gray-800 mb-6">AERIES 2FA Reset Login</h1>
                    <div class="mb-4">
                        <label class="block text-gray-700 text-sm font-bold mb-2" for="domain">
                            Domain
                        </label>
                        <input class="shadow-sm appearance-none border rounded-lg w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-500" id="domain" name="domain" type="text" placeholder="domain" required>
                    </div>
                    <div class="mb-6">
                        <label class="block text-gray-700 text-sm font-bold mb-2" for="login">
                            Login
                        </label>
                        <input class="shadow-sm appearance-none border rounded-lg w-full py-3 px-4 text-gray-700 mb-3 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-500" id="login" name="login" type="login" required>
                        <input type="hidden" name="tech" value="{{ session['username'] }}">
                    </div>
                    <div class="flex items-center justify-between">
                        <button class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-lg focus:outline-none focus:shadow-outline w-full" type="submit">
                            Reset 2FA
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </main>
</body>
</html>
"""

# --- Routes ---

@app.before_request
def before_request():
    session.permanent = True
    session.modified = True

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template_string(HOME_TEMPLATE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        domain = request.form.get('domain')
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password or not domain:
            flash('Domain, Username and password are required.', 'error')
            return redirect(url_for('login'))

        user_dn = f"{username}@{AD_DOMAIN_NAME}"
        #server = Server(AD_SERVER, port=AD_PORT, use_ssl=AD_USE_SSL, get_info=ALL)
        # Configure TLS to accept the encrypted connection without strictly
        # validating the internal domain certificate against public authorities.
        tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)

        server = Server(
            AD_SERVER,
            port=AD_PORT,
            use_ssl=AD_USE_SSL,
            tls=tls_config,
            get_info=ALL
        )
        try:
            with Connection(server, user=user_dn, password=password, authentication=SIMPLE, auto_bind=True) as conn:
                print(f"Authentication successful for user: {username}. Now checking group membership...", flush=True)

                search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
                conn.search(search_base=AD_SEARCH_BASE,
                            search_filter=search_filter,
                            search_scope=SUBTREE,
                            attributes=['memberOf'])

                if conn.entries:
                    user_entry = conn.entries[0]
                    if AD_REQUIRED_GROUP_DN in user_entry.memberOf.values:
                        print(f"User {username} is a member of {AD_REQUIRED_GROUP_DN}. Access granted.", flush=True)
                        session['username'] = username
                        session.permanent = True
                        return redirect(url_for('home'))
                    else:
                        print(f"User {username} is NOT a member of the required group. Access denied.", flush=True)
                        flash('Access denied. You are not in the required security group.', 'error')
                        return redirect(url_for('login'))
                else:
                    print(f"Could not find user object for {username} after successful bind.", flush=True)
                    flash('Authentication error. User object not found.', 'error')
                    return redirect(url_for('login'))

        except LDAPBindError:
            print(f"Authentication failed for user {username}: Invalid credentials.", flush=True)
            flash('Invalid username or password. Please try again.', 'error')
            return redirect(url_for('login'))

        except Exception as e:
            print(f"An unexpected error occurred: {e}", flush=True)
            flash('An error occurred during authentication. Please contact an administrator.', 'error')
            return redirect(url_for('login'))

    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/resetaeries2fa', methods=['GET', 'POST'])
def resetaeries2fa():
    flashmsg = ""
    msg = EmailMessage()

    # Check if configs loaded properly to avoid crashing here
    if not configs:
        flash('System configuration missing. Contact an administrator.', 'error')
        return redirect(url_for('logout'))

    msg['From'] = configs.get('SMTPAddressFrom', 'noreply@auhsdschools.org')
    msg['To'] = 'serveradmins@auhsdschools.org'
    msgsubjectstr = ""
    msgbody=""

    if request.method == 'POST':
        domain = request.form.get('domain')
        login = request.form.get('login')
        tech = request.form.get('tech')

        if not domain or not login:
            flash('A Domain and User Login are required.', 'error')
            return redirect(url_for('login'))
        if "*" in domain or "?" in domain:
            flash('NO WILDCARDS ARE ALLOWED in the DOMAIN field', 'error')
            return redirect(url_for('login'))
        if "*" in login or "?" in login:
            flash('NO WILDCARDS ARE ALLOWED in the LOGIN field', 'error')
            return redirect(url_for('login'))

        server = configs.get('AERIESSQLServer')
        database = configs.get('AERIESDatabase')
        username = configs.get('AERIESTechDept')
        password = configs.get('AERIESTechDeptPW')
        driver = '{ODBC Driver 18 for SQL Server}'
        resetstring= "UPDATE UGN SET MFA = 0 WHERE UN ='" + domain + "\\" + login +"'"

        connection = None
        try:
            connection_string = f'DRIVER={driver};SERVER=tcp:{server},1433;DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=yes;'
            print("Attempting to connect to the database...", flush=True)
            connection = pyodbc.connect(connection_string)
            print("Connection successful!", flush=True)

            cursor = connection.cursor()
            print("\nExecuting query: " + resetstring, flush=True)
            cursor.execute(resetstring)
            connection.commit()
            print(f"Update successful. {cursor.rowcount} row(s) affected.", flush=True)

            row = cursor.rowcount
            if row != 0:
                print(f"\nQuery Result: {row}", flush=True)
                msgbody += "Reset of 2FA for user " + domain + "\\" + login + " by " + tech + " was successful!\n"
                flash('MFA reset on ' + login + ' in the ' + domain + ' was successful!')
            else:
                print("Query did not return any results.", flush=True)
                flash('Was not successful in resetting MFA for ' + login + ' in the ' + domain + ' domain. Check for typo?','error')
                msgbody += "Query on " + domain + "\\" + login + " by " + tech + " did not return any results.\nNo 2FA was reset for any users."

        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            print(f"\nDatabase Error Occurred: SQLSTATE {sqlstate}, Message: {ex}", flush=True)
            msgbody += f"\nDatabase Error Occurred: SQLSTATE: {sqlstate}\nMessage: {ex}"
            flash('An exception occured on the reset the MFA on ' + login + ' in the ' + domain + ' domain.')

        finally:
            if connection:
                print("\nClosing the database connection.", flush=True)
                connection.close()
            print("Connection closed.", flush=True)

            try:
                msg['Subject'] = "AERIES 2FA Reset Tool Results"
                msg.set_content(msgbody)
                s = smtplib.SMTP(configs.get('SMTPServerAddress', 'localhost'))
                s.send_message(msg)
            except Exception as e:
                print(f"Failed to send email: {e}", flush=True)

    return redirect(url_for('logout'))

# --- Main Execution (For local testing without Gunicorn) ---
if __name__ == '__main__':
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=60)
    app.run(host='0.0.0.0', port=5000, debug=True)

    
