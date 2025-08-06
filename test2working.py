#
# Python script to connect to Microsoft SQL Server from an Ubuntu machine.
#
# This script uses the 'pyodbc' library, which requires the Microsoft ODBC Driver for SQL Server.
#
# --------------------------------------------------------------------------------
# -- Step 1: Install Prerequisites on Ubuntu
# --------------------------------------------------------------------------------
#
# Before running this script, you need to install the Microsoft ODBC driver.
# Open your Ubuntu terminal and run the following commands one by one.
#
# 1. Update your package list and install curl:
#    sudo apt-get update
#    sudo apt-get install -y curl
#
# 2. Add the Microsoft package repository key:
#    curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
#
# 3. Register the Microsoft Ubuntu repository:
#    # Note: Replace '20.04' with your Ubuntu version if different (e.g., 18.04, 22.04)
#    curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
#
# 4. Update the package list again and install the driver and development tools:
#    sudo apt-get update
#    sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
#    sudo apt-get install -y unixodbc-dev
#
# --------------------------------------------------------------------------------
# -- Step 2: Install the Python Library
# --------------------------------------------------------------------------------
#
# Now, install the pyodbc library using pip.
#
# pip install pyodbc
#
# --------------------------------------------------------------------------------
# -- Step 3: Run the Python Connection Script
# --------------------------------------------------------------------------------
#
# Update the connection details below with your server's information.
#

import pyodbc,json
from pathlib import Path
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome) as f:
    configs = json.load(f)
        
# --- Connection Details ---
# Replace these placeholders with your actual server details.
server =configs['AERIESSQLServer']
database = configs['AERIESDatabase']
username = configs['AERIESTechDept']
password = configs['AERIESTechDeptPW']
driver = '{ODBC Driver 18 for SQL Server}' # This should be correct if you followed the steps above
print(username)
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
    print("\nExecuting query: 'SELECT @@VERSION'")
    cursor.execute("SELECT @@VERSION")

    # Fetch the result
    row = cursor.fetchone()

    if row:
        print("\nQuery Result:")
        print(row[0])
    else:
        print("Query did not return any results.")

except pyodbc.Error as ex:
    # Handle potential errors
    sqlstate = ex.args[0]
    print(f"\nDatabase Error Occurred:")
    print(f"SQLSTATE: {sqlstate}")
    print(f"Message: {ex}")
    print("\nPlease check the following:")
    print("1. Server name, database, username, and password are correct.")
    print("2. The SQL Server is configured to allow remote connections.")
    print("3. A firewall is not blocking the connection (port 1433 is common).")
    print("4. The ODBC driver was installed correctly.")

finally:
    # --- Close the Connection ---
    # It's important to close the connection when you're done with it.
    if connection:
        print("\nClosing the database connection.")
        connection.close()
        print("Connection closed.")

