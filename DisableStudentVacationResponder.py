import os, sys, pyodbc, shlex, subprocess

#os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.chdir('E:\\PythonTemp')
gamstring2 = "E:\\GAMADV-XTD3\\gam.exe ou_and_children '/Students' vacation off"
p = subprocess.Popen(["powershell.exe",gamstring2],stdout=sys.stdout)
p.communicate()
