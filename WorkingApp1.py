import os
from flask import Flask, request, render_template_string, session, redirect, url_for, flash
from ldap3 import Server, Connection, SIMPLE, ALL, SUBTREE
from ldap3.core.exceptions import LDAPBindError
import ftplib, ssl, sys, os, datetime, json, smtplib, logging
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
# Use a long, random string. You can generate one using:
# python -c 'import os; print(os.urandom(24))'
app.secret_key = os.environ.get('x1a_x01ox97xa8x86x9cxa8xc7x0bxa8Oxafx0bxf3bCfIBx9c', 'x96Tx14xe5xa2x02DRvx11-xe6xf8x86xef^PJxd1rBxda')


# --- Active Directory Configuration ---
# IMPORTANT: Replace these values with your actual AD environment details.
#
# Your AD server's hostname or IP address.
# For high availability, you can use a space-separated list of servers.
# e.g., "ad-server1.mycompany.local ad-server2.mycompany.local"
AD_SERVER = "10.99.0.41"
AD_PORT = 389  # Use 636 for LDAPS (recommended for production)
AD_USE_SSL = False # Set to True for LDAPS
AD_DOMAIN_NAME = "acalanes.k12.ca.us" # The UPN suffix (e.g., user@your-domain.com)

# Base DN for searching users. This is typically the root of your domain.
AD_SEARCH_BASE = "DC=acalanes,DC=k12,DC=ca,DC=us"

# The full Distinguished Name (DN) of the required security group.
# You MUST find this value in your AD. A common format is:
# "CN=GroupName,OU=Security Groups,DC=your-domain,DC=com"
AD_REQUIRED_GROUP_DN = "CN=Aeries2FA,CN=Users,DC=acalanes,DC=k12,DC=ca,DC=us"


# --- HTML Templates ---
# For simplicity, templates are included as strings. In a larger app,
# you would use separate .html files and flask.render_template().

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

            <!-- Flash messages section -->
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
            <!-- Flash messages section -->
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
                        <input class="shadow-sm appearance-none border rounded-lg w-full py-3 px-4 text-gray-700 mb-3 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-500" id="login" name="login" type="login" placeholder="******************" required>
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

@app.route('/')
def home():
    """
    The main protected route.
    Redirects to login if the user is not authenticated.
    """
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template_string(HOME_TEMPLATE)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles the login process.
    GET: Displays the login form.
    POST: Attempts to authenticate the user and check for group membership.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return redirect(url_for('login'))

        user_dn = f"{username}@{AD_DOMAIN_NAME}"
        server = Server(AD_SERVER, port=AD_PORT, use_ssl=AD_USE_SSL, get_info=ALL)

        try:
            # Use a 'with' statement for the connection to ensure it's always closed.
            with Connection(server, user=user_dn, password=password, authentication=SIMPLE, auto_bind=True) as conn:
                print(f"Authentication successful for user: {username}. Now checking group membership...")

                # Search for the user to get their attributes, specifically 'memberOf'
                search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
                conn.search(search_base=AD_SEARCH_BASE,
                            search_filter=search_filter,
                            search_scope=SUBTREE,
                            attributes=['memberOf'])

                # Check if the user was found and get their entry
                if conn.entries:
                    user_entry = conn.entries[0]

                    # The 'memberOf' attribute can be a single value or a list.
                    # We check if the required group DN is in their list of groups.
                    if AD_REQUIRED_GROUP_DN in user_entry.memberOf.values:
                        print(f"User {username} is a member of {AD_REQUIRED_GROUP_DN}. Access granted.")
                        session['username'] = username
                        return redirect(url_for('home'))
                    else:
                        print(f"User {username} is NOT a member of the required group. Access denied.")
                        flash('Access denied. You are not in the required security group.', 'error')
                        return redirect(url_for('login'))
                else:
                    # This case is unlikely if auto_bind succeeded, but it's good practice to handle it.
                    print(f"Could not find user object for {username} after successful bind.")
                    flash('Authentication error. User object not found.', 'error')
                    return redirect(url_for('login'))

        except LDAPBindError:
            # This error occurs if the username/password is incorrect.
            print(f"Authentication failed for user {username}: Invalid credentials.")
            flash('Invalid username or password. Please try again.', 'error')
            return redirect(url_for('login'))

        except Exception as e:
            # Catch other potential exceptions (e.g., server down, config error)
            print(f"An unexpected error occurred: {e}")
            flash('An error occurred during authentication. Please contact an administrator.', 'error')
            return redirect(url_for('login'))

    # For a GET request, just show the login page
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    """
    Logs the user out by clearing the session.
    """
    session.pop('username', None)
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/resetaeries2fa', methods=['GET', 'POST'])
def resetaeries2fa():
    flashmsg = ""
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['SendInfoEmailAddr']
    msgsubjectstr = ""
    msgbody=""
    if request.method == 'POST':
        domain = request.form.get('domain')
        login = request.form.get('login')

        if not domain or not login:
           # flash('A Domain and passLoginword are required.', 'error')
            return redirect(url_for('login'))
        server =configs['AERIESSQLServer']
        database = configs['AERIESDatabase']
        username = configs['AERIESTechDept']
        password = configs['AERIESTechDeptPW']
        driver = '{ODBC Driver 18 for SQL Server}' # This should be correct if you followed the steps above
        resetstring= "UPDATE UGN SET MFA = 0 WHERE UN ='" + domain + "\\" + login +"'"
        # --- Establish Connection ---
        connection = None # Initialize connection to None
        try:
            # Construct the connection string
            connection_string = f'DRIVER={driver};SERVER=tcp:{server},1433;DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=yes;'

            print("Attempting to connect to the database...")
            # Establish the connection
            connection = pyodbc.connect(connection_string)
            print("Connection successful!")

            # Create a cursor object
            cursor = connection.cursor()
            # --- Execute a Query ---
            # You can execute any SQL query here.
            # We'll run a simple query to get the SQL Server version.
            print("\nExecuting query: " + resetstring)
            cursor.execute(resetstring)
            connection.commit()
            print(f"Update successful. {cursor.rowcount} row(s) affected.")
            # Fetch the result
            row = cursor.rowcount
            if row <> 0:
                print("\nQuery Result:")
                print(row)
                msgbody += str(row) + "\n"
                flash('MFA reset on ' + login + ' in the ' + domain + ' domain was successful!')
            else:
                print("Query did not return any results.")
                msgbody += "Query did not return any results.\n"

        except pyodbc.Error as ex:
            # Handle potential errors
            sqlstate = ex.args[0]
            msgbody += "\nDatabase Error Occurred:"
            print(f"\nDatabase Error Occurred:")
            msgbody += "\nDatabase Error Occurred:"
            print(f"SQLSTATE: {sqlstate}")
            msgbody += "SQLSTATE: {sqlstate}"
            print(f"Message: {ex}")
            msgbody += "Message: {ex}"
            print("\nPlease check the following:")
            print("1. Server name, database, username, and password are correct.")
            print("2. The SQL Server is configured to allow remote connections.")
            print("3. A firewall is not blocking the connection (port 1433 is common).")
            print("4. The ODBC driver was installed correctly.")
            flash('An exception occured on the reset the MFA on ' + login + ' in the ' + domain + ' domain.')

        finally:
            # --- Close the Connection ---
            # It's important to close the connection when you're done with it.
            if connection:
                print("\nClosing the database connection.")
                connection.close()
            print("Connection closed.")
            msg['Subject'] = str(configs['SMTPStatusMessage'] + msgsubjectstr)
            msg.set_content(msgbody)
            s = smtplib.SMTP(configs['SMTPServerAddress'])
            s.send_message(msg)            

    return redirect(url_for('home'))
# --- Main Execution ---
if __name__ == '__main__':
    # To run this on your server, you would typically use a production WSGI server
    # like Gunicorn instead of Flask's built-in development server.
    # Example: gunicorn --bind 0.0.0.0:8000 app:app
    #
    # The command below is for development and testing purposes.
    # '0.0.0.0' makes the server accessible from other devices on the network.
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = "edannewitz@auhsdschools.org"
    msgbody = ''
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
    print("Starting Flask development server...")
    print(f"Access the application at http://<your_server_ip>:{5000}")
    app.run(host='0.0.0.0', port=5000, debug=True)
