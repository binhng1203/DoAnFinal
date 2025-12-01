import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
    
    # Cấu hình SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- CẤU HÌNH QUAN TRỌNG NHẤT ---
    # Ép buộc session này chỉ làm việc với schema 'core' và 'public'
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "options": "-c search_path=core,public"
        }
    }
    
    # Cấu hình JWT
    JWT_SECRET_KEY = os.environ.get("SECRET_KEY")