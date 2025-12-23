from src.extensions import ma
from marshmallow import fields, validate

class RegisterSchema(ma.Schema):
    # Validate dữ liệu đầu vào cho API đăng ký
    fullname = fields.String(required=True, validate=validate.Length(min=2))
    username = fields.String(required=True, validate=validate.Length(min=3))
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=8))
    role_name = fields.String(required=True)  # Người dùng gửi lên tên Role (ví dụ: "Test Engineer")

class LoginSchema(ma.Schema):
    # Validate dữ liệu đầu vào cho API đăng nhập
    username = fields.String(required=True)
    password = fields.String(required=True)

class UserResponseSchema(ma.Schema):
    # Định dạng dữ liệu trả về (ẩn password_hash)
    user_id = fields.String()
    fullname = fields.String()
    username = fields.String()
    email = fields.String()
    is_active = fields.Boolean()
    # Nếu muốn trả về danh sách role
    roles = fields.List(fields.Nested(lambda: RoleSchema(only=("role_name",))))

class RoleSchema(ma.Schema):
    role_name = fields.String()