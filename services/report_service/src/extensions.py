from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_jwt_extended import JWTManager
from flask_pymongo import PyMongo

db = SQLAlchemy()
ma = Marshmallow()
jwt = JWTManager()
mongo = PyMongo()