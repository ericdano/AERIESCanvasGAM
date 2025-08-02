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

This script needs to have SQL read access to the following tables in AERIES (we are hosted)
CRS, MST, FTF, STF

This script also uses Pandas for Python. I find Pandas an incredible tool to be able to process datasets easily. It does most all of the heavy
lifting here.


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

    """
    Get Data from AERIES
    
    msgbody += 'Using Database->' + str(configs['AERIESSQLServer']) + '\n'
    WasThereAnError = False

    # Sandbox was only used in 2024 because AERIES roll over was not completed
    #    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServerSandbox'] + ";DATABASE=" + configs['AERIESDatabaseSB'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"
    connection_string = "DRIVER={SQL Server};SERVER=" + configs['AERIESSQLServer'] + ";DATABASE=" + configs['AERIESDatabase'] + ";UID=" + configs['AERIESUsername'] + ";PWD=" + configs['AERIESPassword'] + ";"

    connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
    engine = create_engine(connection_url)
    
    #MHS Query
    '''
    #sql_query = pd.read_sql_query("""SELECT CRS.CN AS CourseID, CRS.CO AS CourseTitle, 
                                      MST.SC AS School, MST.SE AS SectionNum, MST.SE AS ShortTitle, FTF.STI AS CourseNum, MST.CN AS CourseName, STF.LN AS LastName FROM MST INNER JOIN SSE ON MST.SC = SSE.SC AND MST.SE = SSE.SE INNER JOIN FTF ON MST.FSQ = FTF.SQ INNER JOIN STF ON SSE.ID = STF.ID INNER JOIN CRS ON MST.CN = CRS.CN WHERE MST.DEL = 0 AND (MST.CN <> 'OS535E' AND MST.CN <> 'PREPTO' AND MST.CN <> 'O0535E' AND MST.CN <> 'O0544E') ORDER BY SCHOOL, LASTNAME, COURSENAME, SECTIONNUM""", engine)
    # Think the above is not right, the stuff below, by School, is what you should use
    #LLHS Query
    #sql_query = pd.read_sql_query("""SELECT CRS.CN AS CourseID, CRS.CO AS CourseTitle, MST.SC AS School, MST.SE AS SectionNum, MST.SE AS ShortTitle, FTF.STI AS CourseNum, MST.CN AS CourseName, STF.LN AS LastName FROM MST INNER JOIN SSE ON MST.SC = SSE.SC AND MST.SE = SSE.SE INNER JOIN FTF ON MST.FSQ = FTF.SQ INNER JOIN STF ON SSE.ID = STF.ID INNER JOIN CRS ON MST.CN = CRS.CN WHERE MST.SC IN (1,2,3,4,6,7) AND MST.DEL = 0 AND (MST.CN <> 'OS535E' AND MST.CN <> 'PREPTO' AND MST.CN <> 'O0535E' AND MST.CN <> 'O0544E' AND MST.CN <> 'Z5011N' AND MST.CN <> 'Z5016N' AND MST.CN <> 'Z5017N') ORDER BY SCHOOL, LASTNAME, COURSENAME, SECTIONNUM""",engine)
    #sql_query = pd.read_sql_query("""SELECT CRS.CN AS CourseID, CRS.CO AS CourseTitle, MST.SC AS School, MST.SE AS SectionNum, MST.SE AS ShortTitle, FTF.STI AS CourseNum, MST.CN AS CourseName, STF.LN AS LastName FROM MST INNER JOIN SSE ON MST.SC = SSE.SC AND MST.SE = SSE.SE INNER JOIN FTF ON MST.FSQ = FTF.SQ INNER JOIN STF ON SSE.ID = STF.ID INNER JOIN CRS ON MST.CN = CRS.CN WHERE MST.SC IN (6) AND MST.DEL = 0 AND (MST.CN <> 'OS535E' AND MST.CN <> 'PREPTO' AND MST.CN <> 'O0535E' AND MST.CN <> 'O0544E' AND MST.CN <> 'Z5011N' AND MST.CN <> 'Z5016N' AND MST.CN <> 'Z5017N') ORDER BY SCHOOL, LASTNAME, COURSENAME, SECTIONNUM""",engine)
    '''
    #print(sql_query)
    sql_query["SIS_ID"] = "2026~" + sql_query["School"].astype(str) + "_" + sql_query["SectionNum"].astype(str)
    #sql_query["NewCourseTitle"] = "25-26 " + sql_query["CourseTitle"].astype(str) + " - " + sql_query["LastName"] + " " + sql_query['CourseNum']
    sql_query["NewCourseTitle"] = "25-26 " + sql_query["CourseTitle"].astype(str) + " - " + sql_query["LastName"] 
    sql_query["NewCourseTitleSort"] = "25-26 " + sql_query["CourseTitle"].astype(str) + " - " + sql_query["LastName"]
    sql_query["NewCourseSectionData"] = sql_query["SectionNum"].astype(str) + " - " + sql_query["CourseTitle"].astype(str)
    sql_query.to_csv('export.csv')
    #print(sql_query)

    #-----Canvas Info
    #sql_query.to_csv('export2.csv')
    """
    # Using BETA URL 
    Canvas_API_URL = configs['CanvasBETAAPIURL']
    #Canvas_API_URL = configs['CanvasAPIURL']
    Canvas_API_KEY = configs['CanvasAPIKey']
    thelogger.info('AERIES Canvas Course Renamer->Connecting to Canvas')
    canvas = Canvas(Canvas_API_URL,Canvas_API_KEY)
    account = canvas.get_account(1)
    """
    This should be run, to prevent issues, by TERM id. 
    So, run all the S ones, then F ones, and then Y ones in whatever order
    Term IDs 
    2026~1_S,2026~1_F,2026~1_Y - LLHS
    2026~2_S,2026~2_F,2026~2_Y - AHS
    2026~3_S,2026~3_F,2026~3_Y - MHS
    2026~4_S,2026~4_F,2026~4_Y - CHS
    2026~6_S,2026~6_F,2026~6_Y - ACIS
    """
    #d = {'Site':['AHS','AHS','LLHS','LLHS','CHS','CHS','MHS','MHS','ACIS','ACIS'],
    #    'Term':['2026~2_S','2026~2_F','2026~1_S','2026~1_F','2026~4_S','2026~4_F','2026~3_S','2026~3_F','2026~6_S','2026~6_F']}
    column_names = ["courseid","coursename","sistermid"]
    TermDF = pd.DataFrame(columns = column_names)
    tempDF = pd.DataFrame(columns = column_names)
    print('Gathering Canvas Courses')
    courses=account.get_courses(include=['term','sis_term_id'])
    # Gather all the Canvas courses in the Terms we need
    for i in courses:
        if i.term['sis_term_id'] in ('2026~1_Y','2026~2_Y','2026~3_Y','2026~4_Y','2026~64_Y'):
            print(i.id," ",i.name," ",i.term['sis_term_id'])
            tempDF = pd.DataFrame([{'courseid':i.id,
                                    'coursename':i.name,
                                    'sistermid':i.term['sis_term_id']}])
            TermDF = pd.concat([TermDF,tempDF],axis=0, ignore_index=True)
    print('These are the courses')
    print(TermDF)
    TermDF.to_csv('termdump2025.csv',index=False)
    # After DeCrossListing, now you lets go through by Campus and Term and
    # cross list classes
    TermDF.sort_values(by=['coursename','sistermid'], inplace = True)
    print(TermDF)
    bool_series = TermDF.duplicated(['coursename','sistermid'], keep='first')
    TermDF['Dup'] = bool_series
    print(TermDF)
    TermDF.to_csv('termdumpBOOL2025.csv',index=False)
    exit(1)
    CurrentMasterSectionSIS_ID = 0
    CurrentMasterSectionCourseName = ""
    for i in TermDF.index:
        if TermDF['Dup'][i] == False:
            try:
                CurrentMasterSectionSIS_ID =  canvas.get_course(TermDF['courseid'][i])
                theterm = TermDF['sistermid'][i]
                CurrentMasterSectionCourseName = TermDF['coursename'][i]
                theterm2 = theterm[-1]
                if theterm2 == "S":
                    CurrentMasterSectionSimpleCourseName = TermDF['coursename'][i] + " - Spring"
                elif theterm2 == "F":
                    CurrentMasterSectionSimpleCourseName = TermDF['coursename'][i] + " - Fall"
                else:
                    CurrentMasterSectionSimpleCourseName = TermDF['coursename'][i]
                print('Found a potential class->' + str(TermDF['courseid'][i]))
                msgbody += ('Found a potential class->' + str(TermDF['courseid'][i]) + ' ' + TermDF['coursename'][i] + '\n')
            except CanvasException as f:
                if str(f) == "Not Found":
                    print("Panic - Look up of Course SIS_ID " + str(TermDF['courseid'][i]) + " does not seem to be in Canvas but is in AERIES")
                    msgbody += "Panic - Look up of Course SIS_ID " + str(TermDF['courseid'][i]) + " does not seem to be in Canvas but is in AERIES\n"
        elif TermDF['Dup'][i] == True:
            # Here, we seem to have a course that should be cross listed
            # we have the SIS_ID of the FIRST Canvas course, and we need to rename it, getting rid of the P2 or whatever after it
            try:
                course = canvas.get_course(TermDF['courseid'][i])
                sections = course.get_sections()
                #cross list the section
                #for section in sections:
                #    new_section = section.cross_list_section(CurrentMasterSectionSIS_ID)
                print('Cross listed ' + str(TermDF['courseid'][i]) + ' to ' + str(CurrentMasterSectionSIS_ID) + ' ' + CurrentMasterSectionCourseName)
                msgbody += 'Crosslisted ->' + str(TermDF['courseid'][i]) + ' ' + TermDF['coursename'][i] + ' to SIS_ID->' + str(CurrentMasterSectionSIS_ID) + ' ' + CurrentMasterSectionCourseName + '\n'
                # Rename the course title of the section we are cross listing
                '''
                try:
                    course.update(course={'course_code': CurrentMasterSectionSimpleCourseName,
                                            'name': CurrentMasterSectionSimpleCourseName})
                except CanvasException as q:
                    if str(q) == "Not Found":
                        print("PANIC - Course SIS_ID " + str(TermDF['courseid'][i]) + " seems not to be in Canvas but is in AERIES")
                        msgbody += "PANIC - Course SIS_ID " + str(TermDF['courseid'][i])+ " seems not to be in Canvas but is in AERIES\n"
                #Rename the 'Master Class'
                try:
                    CourseToRename = canvas.get_course(CurrentMasterSectionSIS_ID)
                    CourseToRename.update(course={'course_code': CurrentMasterSectionSimpleCourseName,
                                            'name': CurrentMasterSectionSimpleCourseName})
                except CanvasException as e:
                    if str(e) == "Not Found":
                        print("PANIC - Course SIS_ID " + str(CurrentMasterSectionSIS_ID) + " seems not to be in Canvas but is in AERIES")
                        msgbody += "PANIC - Course SIS_ID " + str(CurrentMasterSectionSIS_ID) + " seems not to be in Canvas but is in AERIES\n"
                '''
            except CanvasException as g:
                if str(g) == "Not Found":
                    print("PANIC - Potential course for cross reference, Course SIS_ID " + str(CurrentMasterSectionSIS_ID) + " seems not to be in Canvas but is in AERIES")
                    msgbody += "PANIC - Potential course for cross reference, Course SIS_ID " + str(CurrentMasterSectionSIS_ID) + " seems not to be in Canvas but is in AERIES\n"
        else:
            print('Error!')
            exit(1)
    
    exit(1)
    #
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
    exit(1)
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
    """
    # Courses generated by AERIES into Canvas have a Section with them. We need to create the sections for sample data
    # SAMPLE DATA STUFF - In production we should NOT be messing with Section names and stuff
    """
    for i in sql_query.index:
        print('Adding Section to ' + str(sql_query['SIS_ID'][i]) )
        course = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
        course.create_course_section(course_section={"name":sql_query['NewCourseSectionData'][i],
                                                     "sis_section_id":sql_query['SIS_ID'][i]})
    exit(1)
    ---------------------------------------------------------
    # Fix for not having SIS_ID in the section
    # Don't need to run, saved for historical reference
    
    for i in sql_query.index:
        course = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
        sections = course.get_sections()
        print("Course - " + str(sql_query['SIS_ID'][i]))
        for section in sections:
            print(section.name +" id - " + str(section.id))
            section.edit(course_section={"sis_section_id":sql_query['SIS_ID'][i]})
    ---------------------------------------------------------
 

    sql_query.sort_values(by=['CourseName','NewCourseTitleSort','CourseNum'], inplace = True)
    print(sql_query)
    bool_series = sql_query.duplicated(['CourseName','NewCourseTitleSort'], keep='first')
    print(bool_series)
    sql_query['Dup'] = bool_series
    print(sql_query)
    sql_query.to_csv('exportbool.csv')

    # -----------------------
    # This just sees what sections are related in each course
    # each course has to have a section
    #
    for i in sql_query.index:
        course = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
        sections = course.get_sections()
        print("Course - " + str(sql_query['SIS_ID'][i]))
        for section in sections:
            print(section.name +" id - " + str(section.id))


    #------------------------------------------------------
    # Rename Courses
    # This takes the inital AERIES data and renames classes
    #----------------------
    for i in sql_query.index:
        try:
            CourseToRename = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
            print("Renaming course " + str(sql_query['SIS_ID'][i]) + " to " + str(sql_query['NewCourseTitle'][i]))
            CourseToRename.update(course={'course_code': sql_query['NewCourseTitle'][i],
                                          'name': sql_query['NewCourseTitle'][i]})
        except CanvasException as e:
            if str(e) == "Not Found":
                print("PANIC - Course SIS_ID " + str(sql_query['SIS_ID'][i]) + " seems not to be in Canvas but is in AERIES")
                msgbody += "PANIC - Course SIS_ID " + str(sql_query['SIS_ID'][i]) + " seems not to be in Canvas but is in AERIES\n"
   
    exit(1)
    
    CurrentMasterSectionSIS_ID = 0
    CurrentMasterSectionCourseName = ""


    # -----------------------
    # Cross listing
    for i in sql_query.index:
        if sql_query['Dup'][i] == False:
            try:
                CurrentMasterSectionSIS_ID =  canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
                CurrentMasterSectionCourseName = sql_query['NewCourseTitle'][i]
                CurrentMasterSelectionSimpleCourseName = sql_query['NewCourseTitleSort'][i]
                print('Found a potential class->' + str(sql_query['SIS_ID'][i]))
                msgbody += ('Found a potential class->' + str(sql_query['SIS_ID'][i]) + ' ' + sql_query['NewCourseTitle'][i] + '\n')
            except CanvasException as f:
                if str(f) == "Not Found":
                    print("Panic - Look up of Course SIS_ID " + str(sql_query['SIS_ID'][i]) + " does not seem to be in Canvas but is in AERIES")
                    msgbody += "Panic - Look up of Course SIS_ID " + str(sql_query['SIS_ID'][i]) + " does not seem to be in Canvas but is in AERIES\n"
        elif sql_query['Dup'][i] == True:
            # Here, we seem to have a course that should be cross listed
            # we have the SIS_ID of the FIRST Canvas course, and we need to rename it, getting rid of the P2 or whatever after it
            try:
                course = canvas.get_course(sql_query['SIS_ID'][i],use_sis_id=True)
                sections = course.get_sections()
                #cross list the section
                for section in sections:
                    new_section = section.cross_list_section(CurrentMasterSectionSIS_ID)
                print('Cross listed ' + str(sql_query['SIS_ID'][i]) + ' to ' + str(CurrentMasterSectionSIS_ID) + ' ' + CurrentMasterSectionCourseName)
                msgbody += 'Crosslisted ->' + str(sql_query['SIS_ID'][i]) + ' ' + sql_query['NewCourseTitle'][i] + ' to SIS_ID->' + str(CurrentMasterSectionSIS_ID) + ' ' + CurrentMasterSectionCourseName + '\n'
                # Rename the course title of the section we are cross listing
                try:
                    course.update(course={'course_code': CurrentMasterSelectionSimpleCourseName,
                                            'name': CurrentMasterSelectionSimpleCourseName})
                except CanvasException as q:
                    if str(q) == "Not Found":
                        print("PANIC - Course SIS_ID " + str(sql_query['SIS_ID'][i]) + " seems not to be in Canvas but is in AERIES")
                        msgbody += "PANIC - Course SIS_ID " + str(sql_query['SIS_ID'][i])+ " seems not to be in Canvas but is in AERIES\n"
                #Rename the 'Master Class'
                try:
                    CourseToRename = canvas.get_course(CurrentMasterSectionSIS_ID)
                    CourseToRename.update(course={'course_code': CurrentMasterSelectionSimpleCourseName,
                                            'name': CurrentMasterSelectionSimpleCourseName})
                except CanvasException as e:
                    if str(e) == "Not Found":
                        print("PANIC - Course SIS_ID " + str(CurrentMasterSectionSIS_ID) + " seems not to be in Canvas but is in AERIES")
                        msgbody += "PANIC - Course SIS_ID " + str(CurrentMasterSectionSIS_ID) + " seems not to be in Canvas but is in AERIES\n"
            except CanvasException as g:
                if str(g) == "Not Found":
                    print("PANIC - Potential course for cross reference, Course SIS_ID " + str(CurrentMasterSectionSIS_ID) + " seems not to be in Canvas but is in AERIES")
                    msgbody += "PANIC - Potential course for cross reference, Course SIS_ID " + str(CurrentMasterSectionSIS_ID) + " seems not to be in Canvas but is in AERIES\n"
        else:
            print('Error!')
            exit(1)
"""
    print("Done!")
    msg['Subject'] = str(configs['SMTPStatusMessage'] + " Canvas Renamer and Crosslister " + datetime.datetime.now().strftime("%I:%M%p on %B %d, %Y"))
    end_of_timer = timer()
    msgbody += '\n\n Elapsed Time=' + str(end_of_timer - start_of_timer) + '\n'
    msg.set_content(msgbody)
    s = smtplib.SMTP(configs['SMTPServerAddress'])
    s.send_message(msg)