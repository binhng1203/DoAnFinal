import os
from pathlib import Path
import environ

# 1. Định nghĩa đường dẫn gốc (Base Directory)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# 2. Khởi tạo thư viện đọc biến môi trường
env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# 3. Các cấu hình bảo mật cơ bản
SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# 4. Các ứng dụng được cài đặt
INSTALLED_APPS = [
    
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Thư viện bên thứ 3
    "rest_framework",
    "rest_framework_simplejwt", 

    # Ứng dụng nội bộ (Project Service Logic)
    "src.apps.management", 
    "src.apps.core",
]

# 5. Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = "src.config.urls"

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = "src.config.wsgi.application"
ASGI_APPLICATION = "src.config.asgi.application"

# 6. DATABASE CONFIGURATION (QUAN TRỌNG NHẤT)
DATABASES = {
    # Mặc định kết nối localhost nếu không có biến môi trường (dành cho chạy code thủ công)
    # Khi chạy docker, biến DATABASE_URL trong .env sẽ ghi đè giá trị này
    "default": env.db(
        "DATABASE_URL", 
        default="postgres://app_user:app_password@localhost:5432/final"
    )
}

# Cấu hình Schema Isolation:
# Ép PostgreSQL tìm bảng trong schema 'management' trước, sau đó mới đến 'public'.
# Điều này đảm bảo bảng 'django_migrations' và các bảng nghiệp vụ nằm đúng chỗ.
DATABASES["default"]["OPTIONS"] = {
    "options": "-c search_path=management,public"
}

# 7. Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
]

# 8. Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# 9. Static files
STATIC_URL = 'static/'

# 10. Default Primary Key Field Type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 11. Cấu hình DRF (Django Rest Framework)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

SIMPLE_JWT = {
    "SIGNING_KEY": env("DJANGO_SECRET_KEY"), 
    
    # Thuật toán ký (Mặc định HS256)
    "ALGORITHM": "HS256",
    
    # Header trong request. VD: Authorization: Bearer <token>
    "AUTH_HEADER_TYPES": ("Bearer",),
    
    # Mapping user_id từ token vào model
    "USER_ID_FIELD": "user_id",   # Tên cột trong DB (UUID)
    "USER_ID_CLAIM": "user_id",   # Tên field trong payload của Token
}

# Cấu hình User Model trỏ về User ảo vừa tạo
AUTH_USER_MODEL = "core.User"
