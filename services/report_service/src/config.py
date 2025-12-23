import os

class Config:   
    # 1. Database URI
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/proactive_healing_db")
    
    # 2. Session này ưu tiên tìm trong schema 'custom_analytics'
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "options": "-c search_path=custom_analytics,public"
        }
    }
    
    # 3. JWT Secret Key
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")