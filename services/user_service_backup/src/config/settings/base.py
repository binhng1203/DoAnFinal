import os
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
env = environ.Env()
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
    "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "rest_framework","rest_framework_simplejwt",
    "src.apps.core",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 
    'django.contrib.messages.middleware.MessageMiddleware', 
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTH_USER_MODEL = "core.User"

DATABASES = {
    # env.db() sẽ đọc chuỗi kết nối từ file .env
    "default": env.db("DATABASE_URL", default="postgres://app_user:app_password@localhost:5432/final")
}

# --- THÊM ĐOẠN NÀY NGAY DƯỚI BIẾN DATABASES ---
DATABASES["default"]["OPTIONS"] = {
    # Lệnh này cực kỳ quan trọng:
    # Nó ép mọi query của User Service tự động thêm tiền tố "core."
    # Ví dụ: select * from users -> select * from core.users
    "options": "-c search_path=core,public"
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Ưu tiên BCrypt cho password_hash
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.BCryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

TIME_ZONE = "UTC"
USE_TZ = True

ROOT_URLCONF = "src.config.urls"
WSGI_APPLICATION = "src.config.wsgi.application"
ASGI_APPLICATION = "src.config.asgi.application"

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

STATIC_URL = "static/"

LOGGING = {
  "version": 1,
  "handlers": {"console": {"class": "logging.StreamHandler"}},
  "root": {"handlers": ["console"], "level": "INFO"},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SIMPLE_JWT = {
    "USER_ID_FIELD": "user_id",
    "USER_ID_CLAIM": "user_id",
}