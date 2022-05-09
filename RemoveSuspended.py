import pandas as pd
import os, sys, pyodbc, shlex, subprocess, gam, datetime, json, smtplib, logging



#/bin/sh
#Shell script remove suspended users from groups
#alias gam="/usr/local/gamadv-xtd3/gam"
#/usr/local/gamadv-xtd3/gam print users query isSuspended=true | /usr/local/gamadv-xtd3/gam csv - gam user ~primaryEmail delete groups

if __name__ == '__main__':
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
