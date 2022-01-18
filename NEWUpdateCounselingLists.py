import pandas as pd
import os, sys, pyodbc, shlex, subprocess

#os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.chdir('E:\\PythonTemp')
#populate a table with counselor parts
counselors = [ ('ahs','todd'),
                ('ahs','meadows'),
                ('ahs','schonauer'),
                ('ahs','martin'),
                ('chs','turner'),
                ('chs','dhaliwal'),
                ('chs','santellan'),
                ('chs','magno'),
                ('llhs','wright'),
                ('llhs','feinberg'),
                ('llhs','constantin'),
                ('llhs','bloodgood'),
                ('llhs','sabeh'),
                ('mhs','vasquez'),
                ('mhs','conners'),
                ('mhs','watson'),
                ('mhs','vasicek') ]

conn = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor = conn.cursor()
sql_query = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
for EM, SEM in sql_query.groupby('EM'):
    filename = str(EM).replace("@auhsdschools.org","")+"ALL.csv"
    filename = filename[1:]
    header = ["SEM"]
    SEM.to_csv(filename, index = False, header = False, columns = header)
conn2 = pyodbc.connect('Driver={SQL Server};'
                      'Server=SATURN;'
                      'Database=DST21000AUHSD;'
                      'Trusted_Connection=yes;')
cursor2 = conn.cursor()
sql_query2 = pd.read_sql_query('SELECT ALTSCH.ALTSC, STU.LN, STU.SEM, STU.GR, STU.CU, TCH.EM FROM STU INNER JOIN TCH ON STU.SC = TCH.SC AND STU.CU = TCH.TN INNER JOIN ALTSCH ON STU.SC = ALTSCH.SCID WHERE (STU.SC < 5) AND STU.DEL = 0 AND STU.TG = \'\' AND STU.SP <> \'2\' AND STU.CU > 0 ORDER BY ALTSCH.ALTSC, STU.CU, STU.LN',conn)
for EM, SEM in sql_query2.groupby(['EM','GR']):
    filename2 = str(EM).replace("(\'","").replace("@","").replace("\',","").replace(".org ","").replace(")","")+".csv"
    filename2 = filename2[1:]
    header = ["SEM"]
    SEM.to_csv(filename2, index = False, header = False, columns = header)
# Now call gam
for counselor in counselors:
    # Sync Lists for All Students for counselor
    gamstring1 = "E:\\GAMADV-XTD3\\gam.exe update group " + counselor[0] + counselor[1] + "counselinglist sync members file " + "E:\\PythonTemp\\" + counselor[1] + "ALL.csv"
    deletegamstring1 = "erase E:\\PythonTemp\\" + counselor[1] + "ALL.csv"
    p = subprocess.Popen(["powershell.exe",gamstring1],stdout=sys.stdout)
    p.communicate()
    p = subprocess.Popen(["powershell.exe",deletegamstring1],stdout=sys.stdout)
    p.communicate()
    # Sync Lists for Grade 9 for counselor
    gamstring2 = "E:\\GAMADV-XTD3\\gam.exe update group " + counselor[0] + counselor[1] + "grade9counselinglist sync members file " + "E:\\PythonTemp\\" + counselor[1] + "auhsdschools9.csv"
    deletegamstring2 = "erase E:\\PythonTemp\\" + counselor[1] + "auhsdschools9.csv"
    p = subprocess.Popen(["powershell.exe",gamstring2],stdout=sys.stdout)
    p.communicate()
    p = subprocess.Popen(["powershell.exe",deletegamstring2],stdout=sys.stdout)
    p.communicate()
    # Sync Lists for Grade 10 for counselor
    gamstring3 = "E:\\GAMADV-XTD3\\gam.exe update group " + counselor[0] + counselor[1] + "grade10counselinglist sync members file " + "E:\\PythonTemp\\" + counselor[1] + "auhsdschools10.csv"
    deletegamstring3 = "erase E:\\PythonTemp\\" + counselor[1] + "auhsdschools10.csv"
    p = subprocess.Popen(["powershell.exe",gamstring3],stdout=sys.stdout)
    p.communicate()
    p = subprocess.Popen(["powershell.exe",deletegamstring3],stdout=sys.stdout)
    p.communicate()
    # Sync Lists for Grade 11 for counselor
    gamstring4 = "E:\\GAMADV-XTD3\\gam.exe update group " + counselor[0] + counselor[1] + "grade11counselinglist sync members file " + "E:\\PythonTemp\\" + counselor[1] + "auhsdschools11.csv" 
    deletegamstring4 = "erase E:\\PythonTemp\\" + counselor[1] + "auhsdschools11.csv"
    p = subprocess.Popen(["powershell.exe",gamstring4],stdout=sys.stdout)
    p.communicate()
    p = subprocess.Popen(["powershell.exe",deletegamstring4],stdout=sys.stdout)
    p.communicate()
    #clear out lists and add student to Grade 12 for counselor
    gamstring5 = "E:\\GAMADV-XTD3\\gam.exe update group " + counselor[0] + counselor[1] + "grade12counselinglist sync members file " + "E:\\PythonTemp\\" + counselor[1] + "auhsdschools12.csv"
    deletegamstring5 = "erase E:\\PythonTemp\\" + counselor[1] + "auhsdschools12.csv"
    p = subprocess.Popen(["powershell.exe",gamstring5],stdout=sys.stdout)
    p.communicate()
    p = subprocess.Popen(["powershell.exe",deletegamstring5],stdout=sys.stdout)
    p.communicate()
