import pandas as pd
import os, sys, pyodbc, shlex, subprocess, gam, datetime, json, smtplib, logging
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

# This scrip pull ALL students from AERIES from a site, and puts them into a Canvas Group
#

def GetAERIESData(thelogger):
    conn = pyodbc.connect('Driver={SQL Server};'
                        'Server=SATURN;'
                        'Database=DST22000AUHSD;'
                        'Trusted_Connection=yes;')
    thelogger.info('All Campus Student Canvas Groups->Connecting To AERIES to get ALL students for Campus')
    cursor = conn.cursor()
    sql_query = pd.read_sql_query('SELECT ID, SEM, SC, GR FROM STU WHERE DEL=0 AND STU.TG = \'\' AND (SC < 8 OR SC = 30)',conn)
    # OLD QUERY sql_query = pd.read_sql_query('SELECT ID, SEM, SC, GR FROM STU WHERE DEL=0 AND STU.TG = \'\' AND (SC < 8 OR SC = 30) AND SP <> \'2\'',conn)

    conn.close()
    thelogger.info('All Campus Student Canvas Groups->Closed AERIES connection')
    sql_query.sort_values(by=['SC'])
    return sql_query


def main():
    start_of_timer = timer()
    confighome = Path.home() / ".Acalanes" / "Acalanes.json"
    with open(confighome) as f:
        configs = json.load(f)
    if configs['logserveraddress'] is None:
        logfilename = Path.home() / ".Acalanes" / configs['logfilename']
        thelogger = logging.getLogger('MyLogger')
        thelogger.basicConfig(filename=str(logfilename), level=thelogger.info)
    else:
        thelogger = logging.getLogger('MyLogger')
        thelogger.setLevel(logging.DEBUG)
        handler = logging.handlers.SysLogHandler(address = (configs['logserveraddress'],514))
        thelogger.addHandler(handler)

    SiteClassesCSV = Path.home() / ".Acalanes" / "CanvasSiteClasses.csv"
    thelogger.info('AllCampusStudentCanvasClass->Loaded config file and logfile started')
    thelogger.info('AllCampusStudentCanvasClass->Loading Class Course List CSV file')
    #prep status (msg) email
    msg = EmailMessage()
    msg['From'] = configs['SMTPAddressFrom']
    msg['To'] = configs['SendInfoEmailAddr']
    msg['Subject'] = "Canvas Catch-all Informational Course Update"
    msgbody = ''
    # The counseling CSV has counselors email address, there sis_id, canvas group and grade
    # Grade can have a field All in it that it will then place into a All students
    # at site group for the counselor
    SiteClassesList = pd.read_csv(SiteClassesCSV)
    WasThereAnError = False
    #populate a table
    AERIESData = GetAERIESData(thelogger)
    #print(AERIESData)
    df = AERIESData.sort_values(by=['SC','GR'], ascending = [True,True])

    Canvas_API_URL = configs['CanvasAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']
    thelogger.info('AUHSD Catchall Course Update->Connecting to Canvas')
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    account = canvas.get_account(1)
    for i in SiteClassesList.index:
        print('Finding for ' + str(SiteClassesList['Site'][i]) + ' ' + str(SiteClassesList['CourseID'][i]) + ' ' + str(SiteClassesList['SectionID'][i]))
        msgbody += 'Finding for ' + str(SiteClassesList['Site'][i]) + ' ' + str(SiteClassesList['CourseID'][i]) + ' ' + str(SiteClassesList['SectionID'][i]) + '\n'
        Newdf = df.loc[(df['SC'] == SiteClassesList['SiteID'][i]) & (df['GR'] == SiteClassesList['GradeLevel'][i])]
        section = canvas.get_section(SiteClassesList['SectionID'][i],include=["students"])
        #json_object = json.loads(section.students)
        #print(type(json_object))
        canvasdf = pd.DataFrame(columns=['ID'])
        #print(section.students)
        df1 = pd.DataFrame()
        for s in section.students:
            #print(s)
            #sprint(s['name'])
            canvasdf = canvasdf.append({'ID' : s['sis_user_id']}, ignore_index=True)
    
        #create sets
        aerieslist = set(pd.to_numeric(Newdf.ID))
        canvaslist = set(pd.to_numeric(canvasdf.ID))
        #diff sets
        studentsinaeriesnotincanvas = aerieslist - canvaslist
        studentsincanvasnotinaeries = canvaslist - aerieslist
        #
        #for currentuserid in studentsincanvasnotinaeries:
        #    print(currentuserid)

        print('Students in Aeries not in Canvas' + str(studentsinaeriesnotincanvas))
        msgbody += 'Students in Aeries not in Canvas' + str(studentsinaeriesnotincanvas) + '\n'
        #part two Enroll Student into Canvas Section
        #for currentuserid in studentsinaeriesnotincanvas:
        #CurrentCourse = 9295
        #CurrentSection = 10041
        #    course = canvas.get_course(CurrentCourse)
        #    user = canvas.get_user(currentuserid)
        #    course.enroll_user(
        #        user,
        #        enrollment_type = "StudentEnrollment",
        #            enrollment={'course_section_id': SiteClassesList['SectionID'][i],
        #                        'enrollment_state': 'active'
        #                    }

        #        )
        print('Students in Canvas not in Aeries' + str(studentsincanvasnotinaeries))
        msgbody += 'Students in Canvas not in Aeries' + str(studentsincanvasnotinaeries) + '\n'

    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    thelogger.info('AUHSD Catchall Course Update->->Sent status message')
    thelogger.info('AUHSD Catchall Course Update->->DONE! - took ' + str(end_of_timer - start_of_timer))
    print('Done!!!')

if __name__ == '__main__':
    main()