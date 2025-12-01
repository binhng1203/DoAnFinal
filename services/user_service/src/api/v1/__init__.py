from flask import Blueprint
from .auth import auth_bp
from .users import users_bp
from .admin import admin_bp

# Tạo một Blueprint cha cho V1
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# Gắn auth vào V1
api_v1.register_blueprint(auth_bp, url_prefix='/auth')
api_v1.register_blueprint(users_bp, url_prefix='/users')
api_v1.register_blueprint(admin_bp, url_prefix='/admin')