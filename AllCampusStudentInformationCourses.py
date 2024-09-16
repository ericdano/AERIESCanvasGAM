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

def GetAERIESData(thelogger,schoolcode,grade,configs):
    # Gets ARIES data by schoolcode and grade level
    thelogger.info('All Campus Student Canvas Groups->Connecting To AERIES to get ALL students for Campus')

    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    the_query = f"""
    SELECT
        ID,
        SEM,
        SC,
        GR
    FROM
        STU
    WHERE
        STU.DEL=0
        AND STU.TG = ''
        AND STU.SC='{schoolcode}'
        AND GR='{grade}'
    """
    engine = create_engine(connection_url)
    with engine.begin() as connection:
        sql_query = pd.read_sql_query(the_query,engine)
        thelogger.info('All Campus Student Canvas Groups->Closed AERIES connection')
    sql_query['ID'] = 'STU_' + sql_query['ID'].astype(str)
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
    MessageSub1 = str(configs['SMTPStatusMessage'] + " AUHSD Canvas Catch-All " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    """
    The Site CSV has the Site Abbreviation, SiteID, Canvas CourseID, Grade Level, and Canvas Section ID
    Site,SiteID,CourseID,GradeLevel,SectionID
    Grade can have a field All in it that it will then place into a All students
    at site group for the counselor
    """
    SiteClassesList = pd.read_csv(SiteClassesCSV)
    msgbody += 'Using Database->' + str(configs['AERIESDatabase']) + '\n'
    # USING BETA CanvasBETAAPIURL
    #Canvas_API_URL = configs['CanvasBETAAPIURL']
    Canvas_API_URL = configs['CanvasAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']
    thelogger.info('AUHSD Catchall Course Update->Connecting to Canvas')
    msgbody += 'AUHSD Catchall Course Update->Connecting to Canvas' + '\n'
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    account = canvas.get_account(1)
    for i in SiteClassesList.index:
        GradeToGet = SiteClassesList['Grade'][i]
        SchoolSite = SiteClassesList['SiteID'][i]
        CanvasSectionID = SiteClassesList['CanvasSectionID'][i]
        # Get AERIES Students for the site
        aeriesSQLData = GetAERIESData(thelogger,SchoolSite,GradeToGet,configs)
        thelogger.info('Getting exisiting users from Course id->' + str(CanvasSectionID))
        print('Getting exisiting users from Course id->' + str(CanvasSectionID))
        # Now go get the group off Canvas
        msgbody += 'Getting exisiting users from Course id->' + str(CanvasSectionID) + '\n'
        # Used to DELETE students from course and sections
        course = canvas.get_course(SiteClassesList['CanvasMainCourseID'][i])
        MainCourseEnrollments = course.get_enrollments(type='StudentEnrollment')
        # used to get students in a section
        section = canvas.get_section(SiteClassesList['CanvasSectionID'][i],include=["students"])
        # make a dataframe that has Student SIS IDs in it
        canvasdf = pd.DataFrame(columns=['ID'])
        print('Section looking at ->' + str(section))
        msgbody += 'Section looking at ->' + str(section) + '\n'
        print('CanvasSectionID->' + str(SiteClassesList['CanvasSectionID'][i]))
        msgbody += 'CanvasSectionID->' + str(SiteClassesList['CanvasSectionID'][i]) + '\n'
        # get sis_user_id's out of Canvas data
        print(section)
        # comment out if loading NEW Courses
        for s in section.students:
            tempDF = pd.DataFrame([{'ID': s['sis_user_id']}])
            canvasdf = pd.concat([canvasdf,tempDF], axis=0, ignore_index=True)
        # End of new Course section
        # add STU_ to AERIES data
        #aeriesSQLData['ID'] = 'STU_' + aeriesSQLData['ID'].astype(str)
        studentsinaeriesnotincanvas = aeriesSQLData['ID'][~aeriesSQLData['ID'].isin(canvasdf['ID'])].unique()
        studentsincanvasnotinaeries = canvasdf['ID'][~canvasdf['ID'].isin(aeriesSQLData['ID'])].unique()
        print('Students in Aeries not in Canvas')
        print(studentsinaeriesnotincanvas)
        print('Students in Canvas not in AERIES')
        print(studentsincanvasnotinaeries)
        # Remove students who should not be in the course first
        for student in studentsincanvasnotinaeries:
            thelogger.info('Canvas Catchall->Looking up student->'+str(student)+' in Canvas')
            msgbody += 'Looking up student->'+str(student)+' in Canvas to delete from course' + '\n'
            print('Looking up student->'+str(student)+' in Canvas to delete from course')
            try:
                user = canvas.get_user(str(student),'sis_user_id')
            except CanvasException as g:
                if str(g) == "Not Found":
                    print('Cannot find user sis_id->'+str(student))
                    msgbody+='<b>Canvas cannot find user sis_id->'+str(student) + ', might be a new student who is not in Canvas yet</b>\n'
                    WasThereAnError = True
                    thelogger.info('Canvas Catchall->Cannot find user sis_id->'+str(student))
            else:
                lookfordelete = False
                try:
                    for stu in MainCourseEnrollments:
                        # You have to loop through all the enrollments for the class and then find the student id in the enrollment then tell it to delete it.
                        if stu.user_id == user.id:
                            lookfordelete = True
                            stu.deactivate(task="delete")
                            print('Deleted student ->'+str(user.id) + ' from course')
                            msgbody += 'Deleted student ->'+str(user.id) + ' from course' + '\n'
                            thelogger.info('Deleted student ->'+str(user.id) + ' from course')   
                except CanvasException as e:
                    if str(e) == "Not Found":
                        print('User not in course CanvasID->' + str(user.id) + ' sis_id->'+ str(student))
                        msgbody += 'User not in course CanvasID->' + str(user.id) + ' sis_id->'+ str(student) + '\n'
                        thelogger.info('Canvas Catchall->Some sort of exception happened when removing student->'+str(student)+' from Group')
                        WasThereAnError = True
                print('Removed Student->'+str(student)+' from Canvas group')
                msgbody += 'Removed Student->'+str(student)+' from Canvas course' + '\n'
                thelogger.info('Canvas Catchall->Removed Student->'+str(student)+' from Canvas group')
        # Now add students to group
        # Get the course then loop adding students
        SectionToAddTo = canvas.get_section(SiteClassesList['CanvasSectionID'][i])
        for student in studentsinaeriesnotincanvas:
            print(student)
            user = canvas.get_user(str(student),'sis_user_id')
            msgbody += 'going to try to add '+ str(student) + ' to section ' + str(SectionToAddTo) + '\n'       
            print(course)
            print(SectionToAddTo.id)
            print(user)
            course.enroll_user(
                                user,
                                enrollment_type = "StudentEnrollment",
                                enrollment={'course_section_id': SectionToAddTo.id,'enrollment_state': 'active','limit_privileges_to_course_section': True}
                            )
            print('Added Student id->'+str(student)+' to Canvas course->' + str(CanvasSectionID))
            msgbody += 'Added Student id->'+str(student)+' to Canvas course->' + str(CanvasSectionID) + '\n'
            thelogger.info('Canvas Catchall->Added Student id->'+str(student)+' to Canvas course->' + str(CanvasSectionID))
    thelogger.info('Canvas Catchall->Closed AERIES connection')
    msgbody += 'Done!'
    end_of_timer = timer()
    if WasThereAnError:
        msg['Subject'] = "Error! - " + MessageSub1
    else:
        msg['Subject'] = MessageSub1
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)
    thelogger.info('Canvas Catchall->Sent Status Message')
    thelogger.info('Canvas Catchall->Done!' + str(end_of_timer - start_of_timer))
    print('Done!!!')
            
if __name__ == '__main__':
    main()