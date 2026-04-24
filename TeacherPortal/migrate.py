import urllib.parse
import pandas as pd
from sqlalchemy import create_engine
import json
from pathlib import Path

# 1. Load your MSSQL Configs
confighome = Path.home() / ".Acalanes" / "Acalanes.json"
with open(confighome, 'r') as f:
    configs = json.load(f)

db_name = configs['CanvasGradesDB']
uid = configs['LocalAERIES_Username']
pwd = configs['LocalAERIES_Password']
server_name = r'AERIESLINK.acalanes.k12.ca.us,30000'

# 2. Build the MSSQL Engine
odbc_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server_name};DATABASE={db_name};UID={uid};PWD={pwd};TrustServerCertificate=yes;"
mssql_params = urllib.parse.quote_plus(odbc_str)
mssql_engine = create_engine(f"mssql+pyodbc:///?odbc_connect={mssql_params}")

# 3. Build the MySQL Engine (Connecting inside the Docker network)
mysql_engine = create_engine("mysql+pymysql://canvas_user:canvas_password@db:3306/canvas_data")

# 4. Migrate the Data
print("Pulling data from local MySQL...")
df = pd.read_sql("SELECT * FROM student_grades", con=mysql_engine)

print(f"Found {len(df)} records. Pushing to Aeries MSSQL...")
df.to_sql(name='student_grades', con=mssql_engine, if_exists='append', index=False)

print("Migration Complete! 🎉")