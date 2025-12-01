from flask import Blueprint
from .projects import projects_bp
from .suites import suites_bp
from .cases import cases_bp

# Tạo Blueprint cho API v1 của Project Service
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

api_v1.register_blueprint(projects_bp, url_prefix='/projects')
api_v1.register_blueprint(suites_bp, url_prefix='/')
api_v1.register_blueprint(cases_bp, url_prefix='/')
