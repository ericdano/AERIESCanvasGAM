import pandas as pd
import requests, json, logging, smtplib, datetime, io
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler

if __name__ == '__main__':
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    StartDate = '2023-04-01'
    EndDate = '2023-08-16'
    '''headers = {'Authorization' : 'user='+userid+'&organizationId='+orgid+'&password='+password+'&apiKey='+apikey}'''
    APIUrl = configs['CyberHighURL'] + configs['CyberHighAPIKey'] + '&StartDate=' + StartDate + '&EndDate=' + EndDate
    #APIUrl = 'https://world.cyberhigh.org/API/Data.asmx/CoursesCompleted?AuthenticationKey=fffd74381a5e06ff46af5ddee&StartDate=2023-04-01&EndDate=2023-08-16'
    #headers = {'Authorization' :  'AuthenticationKey=' + AuthenKey + '&StartDate=' + StartDate + '&EndDate=' + EndDate}
    print(APIUrl)
    r = requests.get(APIUrl)
    print(r)
    print(r.text)