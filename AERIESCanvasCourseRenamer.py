from sqlalchemy.engine import URL
from sqlalchemy import create_engine
import pandas as pd
from pathlib import Path
from timeit import default_timer as timer
import requests, json, logging, smtplib, datetime, sys
from canvasapi import Canvas
from canvasapi.exceptions import CanvasException
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from logging.handlers import SysLogHandler
"""
2024
Script to clean up Canvas from AERIES import. Renames the classes in the format 
24-25 English 1 - Cousins
Where 24-25 is the academic year
English 1 is the course
and Cousins is the instructor's last name

"""

if __name__ == '__main__':
    start_of_timer = timer()
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
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServerSandbox'] + ";DATABASE=" + configs['AERIESDatabaseSB'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    sql_query = pd.read_sql_query("""SELECT CRS.CN AS CourseID, CRS.CO AS CourseTitle, MST.SC AS School, MST.SE AS SectionNum, MST.SE AS ShortTitle, FTF.STI AS CourseNum, MST.CN AS CourseName, STF.LN AS LastName FROM MST INNER JOIN SSE ON MST.SC = SSE.SC AND MST.SE = SSE.SE INNER JOIN FTF ON MST.FSQ = FTF.SQ INNER JOIN STF ON SSE.ID = STF.ID INNER JOIN CRS ON MST.CN = CRS.CN WHERE MST.DEL = 0 AND (MST.CN <> 'OS535E' AND MST.CN <> 'PREPTO' AND MST.CN <> 'O0535E' AND MST.CN <> 'O0544E') ORDER BY SCHOOL, LASTNAME, COURSENAME, SECTIONNUM""", engine)
    #print(sql_query)
    sql_query["SIS_ID"] = "2025~" + sql_query["School"].astype(str) + "_" + sql_query["SectionNum"].astype(str)
    sql_query["NewCourseTitle"] = "24-25 " + sql_query["CourseTitle"].astype(str) + " - " + sql_query["LastName"] + " " + sql_query['CourseNum']
    sql_query["NewCourseTitleSort"] = "24-25 " + sql_query["CourseTitle"].astype(str) + " - " + sql_query["LastName"]
    #sql_query.to_csv('export.csv')
    print(sql_query)
    #-----Canvas Info
    #sql_query.to_csv('export2.csv')
    
    # Using BETA URL 
    Canvas_API_URL = configs['CanvasBETAAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']
    thelogger.info('AERIES Canvas Course Renamer->Connecting to Canvas')
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    account = canvas.get_account(1)
    #Load sample Data (only needed if using Beta and they have blanked out the beta site
    #--------------------------------------
    """
    for i in sql_query.index:
        try:
            classexists = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
        except CanvasException as e:
            if str(e) == "Not Found":
                #course does not exist, create it. This is what we expect
                print("Course not in Canvas, creating " + str(sql_query['SIS_ID'][i]) + " in Canvas")
                TemplateToUse = canvas.get_course("AcalanesDefaultTemplate",use_sis_id=True)
                #subaccount = canvas.get_account(asapcoursestocopy['SubAccount'][i])
                newCourse = account.create_course(
                                    course={'name': sql_query['CourseTitle'][i],
                                    'course_code': sql_query['CourseTitle'][i],
                                    'sis_course_id': sql_query['SIS_ID'][i]}
                                    )
                #'term_id': term_id}
                newCourse.create_content_migration('course_copy_importer', settings={'source_course_id': TemplateToUse.id})                    
                print("created course " + str(sql_query['SIS_ID'][i]) + " in Canvas")
    """
    #------------------------------------------------------
    # Rename Courses
    # This takes the inital AERIES data and renames classes
    #----------------------
    """
    for i in sql_query.index:
        try:
            CourseToRename = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
            print("Renaming course " + str(sql_query['SIS_ID'][i]) + " to " + str(sql_query['NewCourseTitle'][i]))
            CourseToRename.update(course={'course_code': sql_query['NewCourseTitle'][i],
                                          'name': sql_query['NewCourseTitle'][i]})
        except CanvasException as e:
            if str(e) == "Not Found":
                print("PANIC - Course SIS_ID " + str(sql_query['SIS_ID'][i]) + " seems not to be in Canvas but is in AERIES")
    """
    # Reset Sample Data
    # Resets Renamed data back to what it was when AERIES brought it over
    #
    """
    for i in sql_query.index:
        try:
            CourseToRename = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
            print("Renaming course " + str(sql_query['SIS_ID'][i]) + " back to AERIES name " + str(sql_query['CourseTitle'][i]))
            CourseToRename.update(course={'course_code': sql_query['CourseTitle'][i],
                                          'name': sql_query['CourseTitle'][i]})
        except CanvasException as e:
            if str(e) == "Not Found":
                print("PANIC - Course SIS_ID " + str(sql_query['SIS_ID'][i]) + " seems not to be in Canvas but is in AERIES")            
    for i in sql_query.index:
        print('Adding Section to ' + str(sql_query['SIS_ID'][i]) )
        course = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
        course.create_course_section(course_section={"name":sql_query['NewCourseTitle'][i]})
    """
    # Fix for not having SIS_ID in the section
    """
    for i in sql_query.index:
        course = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
        sections = course.get_sections()
        print("Course - " + str(sql_query['SIS_ID'][i]))
        for section in sections:
            print(section.name +" id - " + str(section.id))
            section.edit(course_section={"sis_section_id":sql_query['SIS_ID'][i]})
    """
    #-----------section.edit(----------------------------------------
    #findCross = sql_query[sql_query.duplicated(['CourseName','NewCourseTitle'], keep='first')].sort_values('CourseNum')
    sql_query.sort_values(by=['CourseName','NewCourseTitleSort','CourseNum'], inplace = True)
    print(sql_query)
    bool_series = sql_query.duplicated(['CourseName','NewCourseTitleSort'], keep='first')
    print(bool_series)
    sql_query['Dup'] = bool_series
    print(sql_query)
    #sql_query.to_csv('export3.csv')
    # Cross Listing 
    # Assumption is that this is done once, and therefore we can assume no classes have sections, so we can start at 0 for sections and 
    # increment from there
    CurrentMasterSectionSIS_ID = 0
    CurrentMasterSectionCourseName = ""
    # This just sees what sections are related in each course
    # each course has to have a section
    """
    for i in sql_query.index:
        course = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
        sections = course.get_sections()
        print("Course - " + str(sql_query['SIS_ID'][i]))
        for section in sections:
            print(section.name +" id - " + str(section.id))

    """
    for i in sql_query.index:
        if sql_query['Dup'][i] == False:
            CurrentMasterSectionSIS_ID =  canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
            CurrentMasterSectionCourseName = sql_query['NewCourseTitle'][i]
            print('Found a potential class->' + str(sql_query['SIS_ID'][i]))
            msgbody += ('Found a potential class->' + str(sql_query['SIS_ID'][i]) + ' ' + sql_query['NewCourseTitle'][i] + '\n')
        elif sql_query['Dup'][i] == True:
            course = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
            sections = course.get_sections()
            for section in sections:
                new_section = section.cross_list_section(CurrentMasterSectionSIS_ID)
            print('Cross listed ' + str(sql_query['SIS_ID'][i]) + ' to ' + str(CurrentMasterSectionSIS_ID) + ' ' + CurrentMasterSectionCourseName)
            msgbody += ('Crosslisted ->' + str(sql_query['SIS_ID'][i]) + ' ' + sql_query['NewCourseTitle'][i] + ' to SIS_ID->' + str(CurrentMasterSectionSIS_ID) + ' ' + CurrentMasterSectionCourseName + '\n')
        else:
            print('Error!')
            exit(1)
    print("Done!")
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " Canvas Renamer and Crosslister " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)