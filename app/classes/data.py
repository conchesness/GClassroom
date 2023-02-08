o # This is where all the database collections are defined. A collection is a place to hold a defined 
# set of data like Users, Blogs, Comments. Collections are defined below as classes. Each class name is 
# the name of the data collection and each item is a data 'field' that stores a piece of data.  Data 
# fields have types like IntField, StringField etc.  This uses the Mongoengine Python Library. When 
# you interact with the data you are creating an onject that is an instance of the class.

from sys import getprofile
from tokenize import String
from typing import KeysView
from xmlrpc.client import Boolean

from setuptools import SetuptoolsDeprecationWarning
from app import app
from flask import flash
from flask_login import UserMixin
from mongoengine import FileField, EmailField, DictField, StringField, IntField, ReferenceField, DateTimeField, BooleanField, CASCADE
from flask_mongoengine import Document
import datetime as dt
import jwt
from time import time
from bson.objectid import ObjectId

class User(UserMixin, Document):
    createdate = DateTimeField(defaultdefault=dt.datetime.utcnow)
    gid = StringField(sparse=True, unique=True)
    gname = StringField()
    gprofile_pic = StringField()
    username = StringField()
    fname = StringField()
    lname = StringField()
    email = EmailField()
    image = FileField()
    prononuns = StringField()
    role = StringField()

    meta = {
        'ordering': ['lname','fname']
    }
    
class Blog(Document):
    author = ReferenceField('User',reverse_delete_rule=CASCADE) 
    subject = StringField()
    content = StringField()
    tag = StringField()
    create_date = DateTimeField(default=dt.datetime.utcnow)
    modify_date = DateTimeField()

    meta = {
        'ordering': ['-createdate']
    }

class Comment(Document):
    author = ReferenceField('User',reverse_delete_rule=CASCADE) 
    blog = ReferenceField('Blog',reverse_delete_rule=CASCADE)
    # This could be used to allow comments on comments
    comment = ReferenceField('Comment',reverse_delete_rule=CASCADE)
    content = StringField()
    create_date = DateTimeField(default=dt.datetime.utcnow)
    modify_date = DateTimeField()

    meta = {
        'ordering': ['-createdate']
    }

class GoogleClassroom(Document):
    gcourseid = StringField(unique=True)
    createdate = DateTimeField(default=dt.datetime.utcnow)
    modifydate = DateTimeField(default=dt.datetime.utcnow)
    gcoursedict = DictField()
    rosterdict = DictField()
    courseworkdict = DictField()
    studentsubmissionsdict = DictField()

