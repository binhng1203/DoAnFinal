from src.extensions import ma
from marshmallow import fields, validate, validates_schema, ValidationError

class UserUpdateSchema(ma.Schema):
    fullname = fields.String(validate=validate.Length(min=2))
    # Email và Username có thể cho sửa hoặc không tùy nghiệp vụ (trong US_04 cho sửa username)
    username = fields.String(validate=validate.Length(min=3))
    
    # Các trường đổi mật khẩu (Optional)
    current_password = fields.String(load_only=True)
    new_password = fields.String(validate=validate.Length(min=8), load_only=True)
    confirm_new_password = fields.String(load_only=True)

    @validates_schema
    def validate_password_change(self, data, **kwargs):
        # BR4.4: Nếu có nhập mật khẩu mới
        if data.get("new_password"):
            # 1. Phải có mật khẩu hiện tại
            if not data.get("current_password"):
                raise ValidationError("Current password is required to set a new password", field_name="current_password")
            
            # 2. Mật khẩu xác nhận phải khớp
            if data.get("new_password") != data.get("confirm_new_password"):
                raise ValidationError("New passwords do not match", field_name="confirm_new_password")