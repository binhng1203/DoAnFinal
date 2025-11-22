from rest_framework import serializers
from src.apps.core.models import User, Role, Permission

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    class Meta:
        model = User
        fields = ("user_id", "fullname", "username", "email", "password")
        read_only_fields = ("user_id",)
    def create(self, validated_data):
        pwd = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(pwd)  # hash -> password_hash
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

class UserMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("user_id", "fullname", "username", "email", "created_at", "is_active")

class UserMeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("fullname", "email")

class UserListAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("user_id","fullname","username","email","created_at","is_active")

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("role_id","role_name","description")

class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("permission_id","permission_key","description")

class AssignRoleSerializer(serializers.Serializer):
    role_id = serializers.IntegerField()

