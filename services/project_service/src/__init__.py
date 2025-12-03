from flask import Flask
from .config import Config
from .extensions import db, migrate, jwt, ma, bcrypt

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 1. Khởi tạo các Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)
    bcrypt.init_app(app)

    from src import models
    # 2. Đăng ký Blueprints (Routes)   
    from src.api.v1 import api_v1
    app.register_blueprint(api_v1)

    @app.route("/healthz")
    def health_check():
        return "Project Service (Flask) is OK!", 200

    return app