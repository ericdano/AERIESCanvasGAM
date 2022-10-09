import pandas as pd
import os, sys, shlex, subprocess, datetime, json, smtplib, logging
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from pathlib import Path
from timeit import default_timer as timer
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException

"""
This script pulls ALL students from AERIES. Sorts them by site and grade, and puts them into a Canvas Course for the site,
and section in that course by Grade

"""
def GetAERIESData(thelogger):
    """
    pyodbc is depreciated in Pandas 1.5 moved to sqlalchemy

    conn = pyodbc.connect('Driver={SQL Server};'
                        'Server=SATURN;'
                        'Database=DST22000AUHSD;'
                        'Trusted_Connection=yes;')
    cursor = conn.cursor()
    sql_query = pd.read_sql_query('SELECT ID, SEM, SC, GR FROM STU WHERE DEL=0 AND STU.TG = \'\' AND (SC < 8 OR SC = 30)',conn)
     OLD QUERY sql_query = pd.read_sql_query('SELECT ID, SEM, SC, GR FROM STU WHERE DEL=0 AND STU.TG = \'\' AND (SC < 8 OR SC = 30) AND SP <> \'2\'',conn)
    conn.close()
    """

    thelogger.info('All Campus Student Canvas Groups->Connecting To AERIES to get ALL students for Campus')
    connection_string = "DRIVER={SQL Server};SERVER=SATURN;DATABASE=DST22000AUHSD;Trusted_Connection=yes"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    sql_query = pd.read_sql_query('SELECT ID, SEM, SC, GR FROM STU WHERE DEL=0 AND STU.TG = \'\' AND (SC < 8 OR SC = 30)',engine)
    thelogger.info('All Campus Student Canvas Groups->Closed AERIES connection')
    sql_query.sort_values(by=['SC'])
    return sql_query

def main():
    start_of_timer = timer()
    WasThereAnError = False  
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
    msgbody = ''
    """
    The Site CSV has the Site Abbreviation, SiteID, Canvas CourseID, Grade Level, and Canvas Section ID
    Site,SiteID,CourseID,GradeLevel,SectionID
    Grade can have a field All in it that it will then place into a All students
    at site group for the counselor
    """
    SiteClassesList = pd.read_csv(SiteClassesCSV)
    #populate a table
    AERIESData = GetAERIESData(thelogger)
    #print(AERIESData)
    df = AERIESData.sort_values(by=['SC','GR'], ascending = [True,True])
    StudentsDF = pd.DataFrame(columns=['ID'])
    Canvas_API_URL = configs['CanvasAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']
    thelogger.info('AUHSD Catchall Course Update->Connecting to Canvas')
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    account = canvas.get_account(1)
    for i in SiteClassesList.index:
        print('Finding for ' + str(SiteClassesList['Site'][i]) + ' Grade ' +  str(SiteClassesList['GradeLevel'][i]) + ' Course ID-> ' + str(SiteClassesList['CourseID'][i]) + ' Section ID->' + str(SiteClassesList['SectionID'][i]))
        msgbody += 'Finding for ' + str(SiteClassesList['Site'][i]) + ' Grade ' +  str(SiteClassesList['GradeLevel'][i]) + ' Course ID-> ' + str(SiteClassesList['CourseID'][i]) + ' Section ID->' + str(SiteClassesList['SectionID'][i]) + '\n'
        thelogger.info('AUHSD Catchall Course Update->' + 'Finding for ' + str(SiteClassesList['Site'][i]) + ' Grade ' + str(SiteClassesList['GradeLevel'][i]) + ' Course ID-> ' + str(SiteClassesList['CourseID'][i]) + ' Section ID->' + str(SiteClassesList['SectionID'][i]))
        Newdf = df.loc[(df['SC'] == SiteClassesList['SiteID'][i]) & (df['GR'] == SiteClassesList['GradeLevel'][i])]
        section = canvas.get_section(SiteClassesList['SectionID'][i],include=["students"])
        #print(section.students)
        canvasdf = pd.DataFrame(columns=['ID'])
        for s in section.students:
            # Old call, Pandas 1.5 it is depreciated -> canvasdf = canvasdf.append({'ID' : s['sis_user_id']}, ignore_index=True)
            tempDF = pd.DataFrame([{'ID': s['sis_user_id']}])
            canvasdf = pd.concat([canvasdf,tempDF], axis=0, ignore_index=True)
        #create sets
        #print(canvasdf)
        aerieslist = set(pd.to_numeric(Newdf.ID))
        canvaslist = set(pd.to_numeric(canvasdf.ID))
        #diff sets
        studentsinaeriesnotincanvas = aerieslist - canvaslist
        studentsincanvasnotinaeries = canvaslist - aerieslist
        #
        """
         First go through and REMOVE them from the course and section
         If they are misaligned because they are in the wrong grade, it will add them back to the top course again regardless
        for currentuserid in studentsincanvasnotinaeries:
        """
        print('Students in Canvas not in Aeries' + str(studentsincanvasnotinaeries))
        msgbody += 'Students in Canvas not in Aeries' + str(studentsincanvasnotinaeries) + '\n'
        course = canvas.get_course(SiteClassesList['CourseID'][i])
        enrollments = course.get_enrollments(type='StudentEnrollment')
        print('Going to Delete students from course ' + str(SiteClassesList['CourseID'][i]))
        thelogger.info('AUHSD Catchall Course Update->Removing Users in Canvas but not in AERIES')
        if len(studentsincanvasnotinaeries):
            for e in enrollments:
                if e.sis_user_id is None:
                    print('Null in user id->' + str(e.id))
                    #print(e)
                    msgbody += "Error->Null in user id->" + str(e.id) + '\n'
                    thelogger.error('AUHSD Catchall Course Update->Found null in sis_user_id for user ' + str(e.id))
                    WasThereAnError = True
                elif int(e.sis_user_id) in studentsincanvasnotinaeries:
                    print('Removing student->' + str(e.sis_user_id))
                    msgbody += 'Removing student->' + str(e.sis_user_id) + '\n'
                    thelogger.info('AUHSD Catchall Course Update-> Deleting student->' + str(e.sis_user_id))
                    try:
                        e.deactivate(task="delete") 
                    except CanvasException as exc1:
                        print('Error->' + str(exc1))
                        msgbody += "Error->" + str(exc1) + str(e.sis_user_id) +  + '\n'
                        thelogger.error('AUHSD Catchall Course Update-> Error Deleting student->' + str(e.sis_user_id) + ' Canvas error->') + str(exc1)
                        WasThereAnError = True
                else:
                    thelogger.error('AUHSD Catchall Course Update->sis_user_id not there and sis_user_id is not None type ->' + str(e.id))
                    msgbody += 'AUHSD Catchall Course Update->sis_user_id not there and sis_user_id is not None type ->' + str(e.id) + '\n'
                    WasThereAnError = True
                    pass
        else:
            print('No students in section that are in Canvas but not in Aeries')
            msgbody += 'No students in section that are in Canvas but not in Aeries\n'
            thelogger.info('AUHSD Catchall Course Update-> No students in section that are in Canvas but not in Aeries')
        print('\n')        
        #Enroll Student into Canvas Section
        print('Students in Aeries not in Canvas' + str(studentsinaeriesnotincanvas))
        msgbody += 'Students in Aeries not in Canvas' + str(studentsinaeriesnotincanvas) + '\n'
        if len(studentsinaeriesnotincanvas):
            for currentuserid in studentsinaeriesnotincanvas:
                print('Enrolling student->' + str(currentuserid) + ' into Course ' + str(SiteClassesList['CourseID'][i]) + ' section ' + str(SiteClassesList['SectionID'][i]))
                thelogger.info('AUHSD Catchall Course Update->Adding user ' + str(currentuserid))
                try:
                    user = canvas.get_user(currentuserid,'sis_user_id')
                    course.enroll_user(
                        user,
                        enrollment_type = "StudentEnrollment",
                        enrollment={'enrollment_state': 'active'}
                    )
                    course.enroll_user(
                        user,
                        enrollment_type = "StudentEnrollment",
                        enrollment={'course_section_id': SiteClassesList['SectionID'][i],'enrollment_state': 'active'}
                    )
                except CanvasException as exc2:
                    print('Error->' + str(exc2))
                    msgbody += 'Error->' + str(exc2) + '\n'
                    thelogger.error('AUHSD Catchall Course Update-> Error looking up user sis_user_id->' + str(currentuserid) + ' Canvas error ' + str(exc2))
                    WasThereAnError = True
        else:
            print('No students in section that are in Aeries but not in Canvas')
            msgbody += 'No students in section that are in Aeries but not in Canvas\n'
            thelogger.info('AUHSD Catchall Course Update-> No students in section that are in Aeries but not in Canvas')            
    end_of_timer = timer()
    if WasThereAnError == True:
        msg['Subject'] = "ERROR!! -> Canvas Catch-all Informational Course Update"
    else:
        msg['Subject'] = "Canvas Catch-all Informational Course Update"
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    thelogger.info('AUHSD Catchall Course Update->->Sent status message')
    thelogger.info('AUHSD Catchall Course Update->->DONE! - took ' + str(end_of_timer - start_of_timer))
    print('Done!!!')

if __name__ == '__main__':
    main()