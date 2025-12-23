from flask import Blueprint
from .locators import locators_bp

# Tạo Blueprint rỗng để chạy Migration trước
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

api_v1.register_blueprint(locators_bp, url_prefix='/locators')