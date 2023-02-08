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
    return render_template('gcourse.html', gClass=gClass)


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

@app.route('/roster/<gclassid>')
def roster(gclassid):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    rosterDF = pd.DataFrame(gClass.rosterdict)

    profileDF = pd.json_normalize(rosterDF['profile'])
    rosterDF = pd.concat([rosterDF,profileDF],axis=1)
    rosterDF=rosterDF.drop(['profile', 'id','permissions','name.fullName'], axis=1)

    rosterDF['verifiedTeacher'] = rosterDF['verifiedTeacher'] .fillna("")

    rosterDFHTML = rosterDF.to_html(escape=False)
    rosterDFHTML = Markup(rosterDFHTML.replace('<table border="1" class="dataframe">', '<table border="1" class="table">'))
    return render_template('roster.html',gClass=gClass, rosterDFHTML=rosterDFHTML)

@app.route('/coursework/<gclassid>')
def coursework(gclassid):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    courseWorkDF = pd.DataFrame(gClass.courseworkdict)
    courseWorkDFHTML = courseWorkDF.to_html(escape=False)
    courseWorkDFHTML = Markup(courseWorkDFHTML.replace('<table border="1" class="dataframe">', '<table border="1" class="table">'))
    return render_template('coursework.html',gClass=gClass,courseWorkDFHTML=courseWorkDFHTML)

@app.route('/studsubs/<gclassid>')
def studsubs(gclassid):
    gClass = GoogleClassroom.objects.get(gcourseid=gclassid)
    studSubsDF = pd.DataFrame(gClass.studentsubmissionsdict)
    studSubsDFHTML = Markup(studSubsDF.to_html(escape=False))
    return render_template('studsubs.html',gClass=gClass, studSubsDFHTML=studSubsDFHTML)