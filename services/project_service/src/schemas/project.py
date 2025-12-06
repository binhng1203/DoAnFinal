from src.extensions import ma
from marshmallow import fields, validate

# Schema cho Project
class ProjectSchema(ma.Schema):
    project_id = fields.String(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=1))
    description = fields.String(allow_none=True)
    repo_url = fields.String(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    created_by_user_id = fields.String(dump_only=True, data_key="user_id_create")
    # Role của user hiện tại trong project này (dùng khi list)
    my_role = fields.String(dump_only=True)

# Schema cho việc thêm thành viên (PS_05)
class AddMemberSchema(ma.Schema):
    user_id = fields.UUID(required=True) # ID của user cần thêm
    role = fields.String(validate=validate.OneOf(["Project Admin", "Member"]), load_default="Member")

# Schema hiển thị thông tin thành viên (PS_07)
class MemberResponseSchema(ma.Schema):
    user_id = fields.UUID()
    project_role = fields.String()
    joined_at = fields.DateTime()