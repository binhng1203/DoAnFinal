import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

class User(AbstractBaseUser, PermissionsMixin):
    """
    Đây là Model 'ảo' để map với bảng users trong schema core.
    Project Service CHỈ ĐỌC, không tạo/sửa bảng này.
    """
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="user_id")
    username = models.CharField(max_length=100, unique=True, db_column="username")
    email = models.EmailField(max_length=255, unique=True, db_column="email")
    
    # --- KHẮC PHỤC LỖI TẠI ĐÂY ---
    # Mặc định AbstractBaseUser tìm cột "password".
    # Ta phải map nó sang cột thực tế "password_hash" trong DB.
    password = models.CharField(max_length=255, db_column="password_hash")
    # -----------------------------

    is_active = models.BooleanField(default=True, db_column="is_active")
    is_staff = models.BooleanField(default=False)

    # Field bắt buộc của Django Auth
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        managed = False  # QUAN TRỌNG: Django sẽ không tạo/sửa bảng này
        db_table = '"core"."users"' # Trỏ đúng vào bảng user của User Service