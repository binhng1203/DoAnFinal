from src.extensions import ma
from marshmallow import fields

class AssignRoleSchema(ma.Schema):
    role_id = fields.Integer(required=True)

class RoleSchema(ma.Schema):
    role_id = fields.Integer()
    role_name = fields.String()
    description = fields.String()

class PermissionSchema(ma.Schema):
    permission_id = fields.Integer()
    permission_key = fields.String()
    description = fields.String()