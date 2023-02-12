from flask_login import current_user
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt 
from app import app
from flask import render_template, redirect, session, flash, url_for, Markup, render_template_string
from app.classes.data import User, GoogleClassroom
import mongoengine.errors
import google.oauth2.credentials
import googleapiclient.discovery
from google.auth.exceptions import RefreshError
import datetime as dt
import pandas as pd
import numpy as np
from bson.objectid import ObjectId
from .login import credentials_to_dict, client
import json

# This files gets large dictionaries from google and stores them in a record in the GoogleClassroom
# data collection.  Then, to diplay those dictionaries the routes convert them in to Pandas
# DataFrames. 

# TODO get a mockup of the question you want to ask this data and see how we can display
# the answer

@app.route('/gclasses/list')
def gclasseslist():
    
    gCourses = GoogleClassroom.objects()

    return render_template('gclasses.html',gCourses=gCourses)

@app.route('/gclasses/get')
def gclassesget():

    # setup the Google API access credentials
    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        return redirect(url_for('login'))
    session['credentials'] = credentials_to_dict(client)
    classroom_service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)

    # Get all of the google classes
    try:
        gCourses = classroom_service.courses().list(courseStates='ACTIVE').execute()
    except RefreshError:
        flash("When I asked for the courses from Google Classroom I found that your credentials needed to be refreshed.")
        return redirect(url_for('login'))
    else:
        gCourses = gCourses['courses']

    # Iterate through the classes
    for gCourse in gCourses:
        # get the teacher profile from Google
        GTeacher = classroom_service.userProfiles().get(userId=gCourse['ownerId']).execute()

        # Check to see if this course is saved in OTData
        try:
            editGCourse = GoogleClassroom.objects.get(gcourseid = gCourse['id'])
        except:
            newGCourse = GoogleClassroom(
                gcourseid=gCourse['id'],
                gcoursedict=gCourse
            ).save()
        else:
            editGCourse.update(
                gcoursedict=gCourse
            )
    flash("Google Classroom classes updated")
    return redirect(url_for('gclasseslist'))

@app.route('/gclass/<gclassid>')
def gclass(gclassid):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    gcourseDF = pd.DataFrame(data=gClass.gcoursedict)
    gcourseDF = gcourseDF.T
    #profileDF = pd.json_normalize(rosterDF['profile'])
    #rosterDF = pd.concat([rosterDF,profileDF],axis=1)
    gcourseDF=gcourseDF.drop(['title','alternateLink','calculationType','displaySetting'], axis=1)
    try:
        gcourseDF=gcourseDF.drop(['gradeCategories'], axis=1)
    except:
        pass
    gcourseDF = gcourseDF.rename(columns={"id": "Values"})
    gcourseDFHTML = gcourseDF.to_html(escape=False)
    gcourseDFHTML = Markup(gcourseDFHTML.replace('<table border="1" class="dataframe">', '<table border="1" class="table">'))
    
    return render_template('gcourse.html', gClass=gClass, gcourseDFHTML=gcourseDFHTML)


@app.route("/roster/get/<gclassid>")
def getroster(gclassid):
    
    # Get the Google Classroom from OTData
    try:
        editGClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    except:
        flash(f"There is no Google Classroom with the id {gclassid}")
        return redirect(url_for('gclasseslist'))

    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        return redirect(url_for('login'))    
    session['credentials'] = credentials_to_dict(client)
    classroom_service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)

    # If the index is 0 then we are at the begining of the process and need to 
    # get the roster from Google
    pageToken = None
    try:
        students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()
    except RefreshError:
        flash("When I asked for the courses from Google Classroom I found that your credentials needed to be refreshed.")
        return redirect(url_for('login'))
    gstudents=[]
    while True:
        pageToken = students_results.get('nextPageToken')
        gstudents.extend(students_results['students'])
        if not pageToken:
            break
        students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()
    
    editGClass.update(
        rosterdict=gstudents
    )
    
    return redirect(url_for('gclass',gclassid=gclassid))

@app.route('/studentwork/get/<gclassid>')
def getstudentwork(gclassid):

    # setup the Google API access credentials
    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        return redirect(url_for('login'))

    session['credentials'] = credentials_to_dict(client)

    classroom_service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)
    pageToken=None

    try:
        studSubs = classroom_service.courses().courseWork().studentSubmissions().list(
            courseId=gclassid,
            #states=['TURNED_IN','RETURNED','RECLAIMED_BY_STUDENT'],
            courseWorkId='-',
            pageToken=pageToken
            ).execute()
    except RefreshError:
        flash('Had to reauthorize your Google credentials.')
        return redirect(url_for('login'))
    except Exception as error:
        flash(f"unknown error: {error}")
        return redirect(url_for('index'))
    
    studSubsAll = []
    counter=1
    while True:

        print(counter,pageToken)
        pageToken = studSubs.get('nextPageToken')
        studSubsAll.extend(studSubs['studentSubmissions'])
        if not pageToken:
            break
        studSubs = classroom_service.courses().courseWork().studentSubmissions().list(
            courseId=gclassid,
            #states=['TURNED_IN','RETURNED','RECLAIMED_BY_STUDENT'],
            courseWorkId='-',
            pageToken=pageToken
            ).execute()
        
        counter=counter+1


    editGCourse = GoogleClassroom.objects.get(gcourseid = gclassid)
    editGCourse.update(
        studentsubmissionsdict = studSubsAll
    )
    return redirect(url_for('gclass', gclassid=gclassid))

@app.route('/coursework/get/<gclassid>')
def getCourseWork(gclassid):
    pageToken = None
    assignmentsAll = []

    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        flash("need to refresh your connection to Google Classroom.")
        return redirect(url_for('login'))
    
    session['credentials'] = credentials_to_dict(client)
    classroom_service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)
    try:
        topics = classroom_service.courses().topics().list(
            courseId=gclassid
            ).execute()
    except RefreshError:
        return redirect(url_for('login'))
    except Exception as error:
        flash(f"Got unknown Error: {error}")
        return redirect(url_for('index'))
    
    topics = topics['topic']

    # Topic dictionary
    # [{'courseId': '450501150888', 'topicId': '487477497511', 'name': 'Dual Enrollment', 'updateTime': '2022-05-20T20:55:41.926Z'}, {...}]

    # TODO get all assignments and add as dict to gclassroom record
    while True:
        try:
            assignments = classroom_service.courses().courseWork().list(
                    courseId=gclassid,
                    pageToken=pageToken,
                    ).execute()
        except RefreshError:
            return redirect(url_for('login'))
        except Exception as error:
            flash(f"Got unknown Error: {error}")
            return redirect(url_for('index'))

        try: 
            assignmentsAll.extend(assignments['courseWork'])
        except (KeyError,UnboundLocalError):
            break
        else:
            pageToken = assignments.get('nextPageToken')
            if pageToken == None:
                break

    for ass in assignmentsAll:
        for topic in topics:
            try:
                ass['topicId']
            except:
                ass['topicId'] = None
            if topic['topicId'] == ass['topicId']:
                ass['topic'] = topic['name']
                break

        
    gclassroom = GoogleClassroom.objects.get(gcourseid=gclassid)
    gclassroom.update(courseworkdict = assignmentsAll)
    return redirect(url_for("gclass",gclassid=gclassid))

@app.route('/roster/<gclassid>/<sort>')
@app.route('/roster/<gclassid>')
def roster(gclassid, sort='lname'):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)

    rosterDF = pd.DataFrame(gClass.rosterdict)
    profileDF = pd.json_normalize(rosterDF['profile'])
    rosterDF = pd.concat([rosterDF,profileDF],axis=1)
    rosterDF=rosterDF.drop(['profile', 'courseId', 'id','permissions','name.fullName'], axis=1)
    rosterDF['verifiedTeacher'] = rosterDF['verifiedTeacher'] .fillna("")
    if sort == 'lname':
        rosterDF.sort_values(by=['name.familyName','name.givenName'],inplace=True)
    else:
        rosterDF.sort_values(by=['name.givenName','name.familyName'],inplace=True)
    rosterDF = rosterDF.set_index('userId')
    rosterDFHTML = rosterDF.to_html(escape=False)
    rosterDFHTML = rosterDFHTML.replace('<th>', '<th class="text-start">')
    rosterDFHTML = Markup(rosterDFHTML.replace('<table border="1" class="dataframe">', '<table border="1" class="table">'))
    return render_template('roster.html',gClass=gClass, rosterDFHTML=rosterDFHTML)

@app.route('/coursework/<gclassid>')
def coursework(gclassid):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    courseWorkDF = pd.DataFrame(gClass.courseworkdict)
    dueDateDF = pd.json_normalize(courseWorkDF['dueDate'])
    courseWorkDF = pd.concat([courseWorkDF,dueDateDF],axis=1)  
    courseWorkDF['year'] = courseWorkDF['year'].fillna(0).astype(str).str.replace(".0","",regex=False)
    courseWorkDF['month'] = courseWorkDF['month'].fillna(0).astype(str).str.replace(".0","",regex=False)
    courseWorkDF['day'] = courseWorkDF['day'].fillna(0).astype(str).str.replace(".0","",regex=False)
    courseWorkDF.loc[courseWorkDF['year'] != '0', 'dueDate'] = courseWorkDF['day']+'/'+courseWorkDF['month']+'/'+courseWorkDF['year']
    courseWorkDF=courseWorkDF.drop(['courseId','year','month','day'], axis=1)
    courseWorkDF['dueDate'] = pd.to_datetime(courseWorkDF['dueDate'])   
    courseWorkDF.sort_values(by=['dueDate'],inplace=True)
    courseWorkDF = courseWorkDF.set_index('id')

    courseWorkDFHTML = courseWorkDF.to_html(escape=False)
    courseWorkDFHTML = courseWorkDFHTML.replace('<th>', '<th class="text-start">')
    courseWorkDFHTML = Markup(courseWorkDFHTML.replace('<table border="1" class="dataframe">', '<table border="1" class="table">'))
    return render_template('coursework.html',gClass=gClass,courseWorkDFHTML=courseWorkDFHTML)

@app.route('/studsubs/<gclassid>')
def studsubs(gclassid):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    studSubsDF = pd.DataFrame(gClass.studentsubmissionsdict)
     
    studSubsDFHTML = studSubsDF.to_html(escape=False)
    studSubsDFHTML = studSubsDFHTML.replace('<th>', '<th class="text-start">')
    studSubsDFHTML = Markup(studSubsDFHTML.replace('<table border="1" class="dataframe">', '<table border="1" class="table">'))
    return render_template('studsubs.html',gClass=gClass, studSubsDFHTML=studSubsDFHTML)

@app.route('/gradebook/<gclassid>/<dl>')
@app.route('/gradebook/<gclassid>')
def gradebook(gclassid,dl=0):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    if not gClass.rosterdict or not gClass.courseworkdict or not gClass.studentsubmissionsdict:
        flash(f"{gClass.coursedict.name} is missing at least one of roster, assignments or student submissions.")
        return redirect(url_for('gclass', gclassid=gclassid))
    
    studSubsDF = pd.DataFrame(gClass.studentsubmissionsdict)
    # The following line can be used to drop specific columns from the result
    #studSubsDF=studSubsDF.drop(['submissionHistory','assignmentSubmission','alternateLink'], axis=1)

    courseWorkDF = pd.DataFrame(gClass.courseworkdict)
    # The following line is the opposite of dropping, it is a way to select
    # only the columns you want. Comment it out to see all of the data.
    courseWorkDF = courseWorkDF[['id','title','state','maxPoints','topic']].copy()

    rosterDF = pd.DataFrame(gClass.rosterdict)
    profileDF = pd.json_normalize(rosterDF['profile'])
    rosterDF = pd.concat([rosterDF,profileDF],axis=1)
    rosterDF=rosterDF.drop(['profile', 'courseId', 'id','permissions','name.fullName'], axis=1)
    rosterDF['verifiedTeacher'] = rosterDF['verifiedTeacher'] .fillna("")

    gbDF = pd.merge(
        courseWorkDF,
        studSubsDF,
        how="inner",
        on=None,
        left_on='id',
        right_on='courseWorkId',
        left_index=False,
        right_index=False,
        sort=True,
        suffixes=("_CW", "_Sub"),
        copy=True,
        indicator=False,
        validate=None,
    )

    gbDF = pd.merge(
        rosterDF,
        gbDF,
        how="inner",
        on='userId',
        left_on=None,
        right_on=None,
        left_index=False,
        right_index=False,
        sort=True,
        suffixes=("_ass", "_sub"),
        copy=True,
        indicator=False,
        validate=None,
    )

    if dl == "1":
        gbDF.to_csv('gb/gradebook.csv')
        flash("File downloaded to gb folder.")

    gbDFHTML = gbDF.to_html(escape=False)
    gbDFHTML = gbDFHTML.replace('<th>', '<th class="text-start">')
    gbDFHTML = Markup(gbDFHTML.replace('<table border="1" class="dataframe">', '<table border="1" class="table">'))
    return render_template('gradebook.html',gClass=gClass, gbDFHTML=gbDFHTML)

@app.route('/gbvis/<gclassid>')
@app.route('/gbvis/<gclassid>/<sortValue>')
def gbvis(gclassid, sortValue='lname'):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    if not gClass.rosterdict or not gClass.courseworkdict or not gClass.studentsubmissionsdict:
        flash(f"{gClass.coursedict.name} is missing at least one of roster, assignments or student submissions.")
        return redirect(url_for('gclass', gclassid=gclassid))
    
    #Take the dict out of the db and turn it into a dataframe
    studSubsDF = pd.DataFrame(gClass.studentsubmissionsdict)
    # The following line can be used to drop specific columns from the result
    studSubsDF=studSubsDF.drop(['submissionHistory','assignmentSubmission','alternateLink'], axis=1)

    #Take the dict out of the db and turn it into a dataframe
    courseWorkDF = pd.DataFrame(gClass.courseworkdict)
    # The following line is the opposite of dropping, it is a way to select
    # only the columns you want. Comment it out to see all of the data.
    courseWorkDF = courseWorkDF[['id','title','state','maxPoints','topic']].copy()

    #Take the dict out of the db and turn it into a dataframe
    rosterDF = pd.DataFrame(gClass.rosterdict)
    #profile is a dict in a cell of dataframe, this explodes it as alomuns
    profileDF = pd.json_normalize(rosterDF['profile'])
    #concatenate the two
    rosterDF = pd.concat([rosterDF,profileDF],axis=1)

    #change name.fullName to be last name first if that is the sort order from the url
    if sortValue == 'lname':
        rosterDF['name.fullName'] = rosterDF['name.familyName']+", "+rosterDF['name.givenName']

    #Drop unwanted fields
    rosterDF=rosterDF.drop(['profile', 'courseId', 'id','permissions','name.givenName','name.familyName'], axis=1)
    #remove NaN from a column
    rosterDF['verifiedTeacher'] = rosterDF['verifiedTeacher'] .fillna("")

    # merge two tables on a common ID
    gbDF = pd.merge(
        courseWorkDF,
        studSubsDF,
        how="inner",
        on=None,
        left_on='id',
        right_on='courseWorkId',
        left_index=False,
        right_index=False,
        sort=True,
        suffixes=("_ass", "_sub"),
        copy=True,
        indicator=False,
        validate=None,
    )

    #merge two tables on a common id
    gbDF = pd.merge(
        rosterDF,
        gbDF,
        how="inner",
        on='userId',
        left_on=None,
        right_on=None,
        left_index=False,
        right_index=False,
        sort=True,
        suffixes=("_stu", "_gb"),
        copy=True,
        indicator=False,
        validate=None,
    )
    
    #create a pivot table to show scores for each student on each assignment
    gbDF = gbDF.pivot_table(index="name.fullName", columns="title", values="assignedGrade", aggfunc=["mean"], margins=True, margins_name="Ave")

    #get all the column names and pop the last one off which is an average of all scores.
    #Then use that list to count all the the columns with a score except the ave column
    col_list = list(gbDF)
    col_list.pop()
    gbDF[('','Count')] = gbDF[col_list].count(axis=1)

    #Move the ave and Count columns to the front of the table
    ave = gbDF.pop(("mean","Ave"))
    gbDF.insert(0, ("","Ave"), ave)
    count = gbDF.pop(("","Count"))
    gbDF.insert(1, ("","Count"), count)

    #Drop the Ave row from the bottom of the Dataframe before the sorting
    #when you select a column it is turned into a series so you need to turn it back 
    # into a datafram and then transpose it so it can be put back onto the final dataframe after sorting
    ave = pd.DataFrame(gbDF.loc['Ave']).transpose()
    notAve = gbDF.drop(['Ave'])

    print(gbDF.columns)
    if sortValue == 'fname' or sortValue == "lname":
        sorted = notAve.sort_values(by=['name.fullName'],ascending=True)
    elif sortValue == "count":
        sorted = notAve.sort_values(by=[('','Count'),'name.fullName'],ascending=True)
    elif sortValue == "ave":
        sorted = notAve.sort_values(by=[('','Ave')],ascending=True) 
    gbDF = pd.concat([sorted,ave])
    #Drop the label at the top of the DF that was created by the pivot table.
    gbDF.columns = gbDF.columns.droplevel(0)

 
    #Lots of styling for the html
    gbDFHTML = gbDF.style\
        .format(precision=2)\
        .set_table_styles([
            {'selector': 'tr:hover','props': 'background-color: yellow; font-size: 1em;'},\
            {'selector': 'th','props': 'background-color: red'}], overwrite=False)\
        .set_properties(subset=['Ave','Count'], **{'font-weight': 'bold'})\
        .format(subset=['Count'], precision=0)\
        .set_sticky(axis="index")\
        .set_sticky(axis="columns")\
        .set_properties(**{'border': '1px black solid !important'})\
        .to_html() 
    # TODO these two lines should be accomplished with the styler like the lines
    # above
    gbDFHTML = gbDFHTML.replace('inherit','white')
    gbDFHTML = gbDFHTML.replace('nan','---')
    gbDFHTML = Markup(gbDFHTML.replace('<table id', '<table class="table" id'))


    return render_template('gradebook.html',gClass=gClass, gbDFHTML=gbDFHTML)