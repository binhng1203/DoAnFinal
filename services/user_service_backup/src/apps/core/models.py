import uuid
from django.db import models
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin

class UserManager(BaseUserManager):
    use_in_migrations = True
    def _create_user(self, username, email, password=None, **extra):
        if not username: raise ValueError("Username required")
        if not email: raise ValueError("Email required")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra)
        if password:
            user.set_password(password)  # ghi vào cột password_hash
        user.save(using=self._db)
        return user
    def create_user(self, username, email, password=None, **extra):
        extra.setdefault("is_active", True)
        return self._create_user(username, email, password, **extra)
    def create_superuser(self, username, email, password=None, **extra):
        extra.setdefault("is_active", True)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create_user(username, email, password, **extra)

class User(AbstractBaseUser, PermissionsMixin):
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="user_id")
    fullname = models.CharField(max_length=100, unique=True, db_column="fullname")
    username = models.CharField(max_length=100, unique=True, db_column="username")
    email = models.EmailField(max_length=255, unique=True, db_column="email")
    password = models.CharField(max_length=255, db_column="password_hash")  # map sang cột password_hash
    created_at = models.DateTimeField(auto_now_add=True, db_column="created_at")
    is_active = models.BooleanField(default=True, db_column="is_active")

    # hỗ trợ admin Django
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    objects = UserManager()

    class Meta:
        db_table = '"core"."users"'

class Role(models.Model):
    role_id = models.AutoField(primary_key=True, db_column="role_id")
    role_name = models.CharField(max_length=50, unique=True, db_column="role_name")
    description = models.TextField(blank=True, null=True, db_column="description")
    class Meta:
        db_table = '"core"."roles"'

class Permission(models.Model):
    permission_id = models.AutoField(primary_key=True, db_column="permission_id")
    permission_key = models.CharField(max_length=100, unique=True, db_column="permission_key")
    description = models.TextField(blank=True, null=True, db_column="description")
    class Meta:
        db_table = '"core"."permissions"'

# Bảng nối (composite PK) -> ORM managed=False, thao tác bằng raw SQL
class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column="user_id", to_field="user_id")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id", to_field="role_id")
    class Meta:
        managed = False
        db_table = '"core"."user_roles"'

class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id", to_field="role_id")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, db_column="permission_id", to_field="permission_id")
    class Meta:
        managed = False
        db_table = '"core"."role_permissions"'

