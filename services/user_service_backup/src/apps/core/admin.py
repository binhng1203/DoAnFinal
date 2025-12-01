from django.contrib import admin
from .models import User, Role, Permission

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("user_id","username","email","fullname","is_active","created_at")
    search_fields = ("username","email","fullname")

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("role_id","role_name")

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("permission_id","permission_key")

