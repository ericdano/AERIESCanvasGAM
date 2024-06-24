from numpy.lib.function_base import _parse_input_dimensions
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
import pandas as pd
from pathlib import Path
import requests, json, logging, smtplib, datetime, sys
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
"""
 Script to rename classes in Canvas that are from the previous term
 We generally are keeping all previous classes in our Canvas rather than deleting them
 However, it is confusing for the teachers to have like 5 ESL Morning classes from different terms in their dashboard
 So, this script will RENAME a class depending on the TERM you are looking for
 The best way to do this is to GRAB all the courses, append the new names to them
 and then go through it again and anything in the TERM ID will be changed to the new name
 run it like this
 python canvas_rename_course_endofterm.py 'SUM2021' 'Summer 2021 -' 'SUM21'
 this will look for your SIS TERM ID of FALL2020 and then prepend the second argument to the class

 suggest commenting out the LAST TWO LINES at the end of this file before you make changes to make sure things are correct!!!!!!!!

 ie the course = canvas.get_course(cid)
 and course.update(course={'name': newname})


def getCanvasCourses(canvasaccount,canvasid):
    logging.info('Starting to rename classes')
    logging.info('going to look for ' + termidlookingfor + 'and prepend ' + prependname + 'to it')
    column_names = ["courseid","coursename","sistermid","newcoursename"]
    df = pd.DataFrame(columns = column_names)
    tempDF = pd.DataFrame(columns = column_names)
    courses=canvasaccount.get_courses(include=['term','sis_term_id'])
    for i in courses:
        if i.term['sis_term_id'] == termidlookingfor:
            #print(i.id," ",i.name," ",i.term['sis_term_id'])
            tempDF = pd.DataFrame([{'courseid':i.id,
                'coursename':i.name,
                'sistermid':i.term['sis_term_id'],
                'newcoursename':prependname + i.name}])
            df = pd.concat([df,tempDF],axis=0, ignore_index=True)
    # Now go through and update the SIS_ID and Course_codes and tack on a suffex and rename the course
    print(df)
    for index, row in df.iterrows():
        bid = row["courseid"]
        c = canvasid.get_course(bid)
        new_sis_id = c.sis_course_id + prependccstr
        newcoursename = prependname + c.name
        #print(new_sis_id)
        #print(course.sis_course_id)
        print("Updating term->",termidlookingfor," courseid:",c.sis_course_id," to ", new_sis_id, " and ",c.name," to ",newcoursename)
        logging.info('Updating term->' + termidlookingfor + ' courseid:' + c.sis_course_id + ' to ' + c.sis_course_id + prependccstr + ' and ' + c.name + ' to ' + newcoursename)
        c.update(course={'course_code':new_sis_id,
                            'sis_course_id':new_sis_id,
                            'name':newcoursename})
    logging.info('Done -- RollOver_classes.py')
    print('Done!')

"""

if __name__ == '__main__':
    #start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    thelogger = logging.getLogger('MyLogger')
    thelogger.setLevel(logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
    thelogger.addHandler(handler)
    #prep status (msg) email
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['SendInfoEmailAddr']
    msgbody = ''
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
    WasThereAnError = False
#LIST SEC MST SSE FTF STF CRS CRS.CN CRS.CO MST.SC MST.SE FTF.STI MST.CN  STF.LN
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServerSandbox'] + ";DATABASE=" + configs['AERIESDatabaseSB'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    sql_query = pd.read_sql_query("""SELECT CRS.CN AS CourseID, CRS.CO AS CourseTitle, MST.SC AS School, MST.SE AS SectionNum, MST.SE AS ShortTitle, FTF.STI AS CourseNum, MST.CN AS CourseName, STF.LN AS LastName FROM MST INNER JOIN SSE ON MST.SC = SSE.SC AND MST.SE = SSE.SE INNER JOIN FTF ON MST.FSQ = FTF.SQ INNER JOIN STF ON SSE.ID = STF.ID INNER JOIN CRS ON MST.CN = CRS.CN WHERE MST.DEL = 0 AND (MST.CN <> 'OS535E' AND MST.CN <> 'PREPTO' AND MST.CN <> 'O0535E' AND MST.CN <> 'O0544E') ORDER BY SCHOOL, LASTNAME, COURSENAME, SECTIONNUM""", engine)
    print(sql_query)
    sql_query["SIS_ID"] = "2025~" + sql_query["School"].astype(str) + "_" + sql_query["SectionNum"].astype(str)
    sql_query["NewCourseTitle"] = "24-25 " + sql_query["CourseTitle"].astype(str) + " - " + sql_query["LastName"]
    #sql_query.to_csv('export.csv')
    print(sql_query)
    #-----Canvas Info
    sql_query.to_csv('export2.csv')
    Canvas_API_URL = configs['CanvasBETAAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']
    thelogger.info('AERIES Canvas Course Renamer->Connecting to Canvas')
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    account = canvas.get_account(1)
    