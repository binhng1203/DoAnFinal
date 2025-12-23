from src.extensions import ma
from marshmallow import fields, validate
from src.schemas.step import TestStepSchema

class TestCaseSchema(ma.Schema):
    case_id = fields.Integer(dump_only=True)
    suite_id = fields.String(dump_only=True) # UUID dạng string
    
    name = fields.String(required=True, validate=validate.Length(min=1, max=255))
    
    # Validate Enum (BR13.2)
    priority = fields.String(validate=validate.OneOf(["Low", "Medium", "High"]))
    type = fields.String(validate=validate.OneOf(["Manual", "Automated"]))
    
    description = fields.String(allow_none=True)
    tags = fields.List(fields.String(), allow_none=True) # Mảng String
    assignee_id = fields.String(allow_none=True)
    
    is_active = fields.Boolean()
    fullscreen_page_name = fields.String(allow_none=True)
    app_version = fields.String(allow_none=True)
    last_run_status = fields.String(dump_only=True)
    
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    created_by = fields.String(dump_only=True)
    updated_by = fields.String(dump_only=True)

    # Nested: Khi get Case sẽ lấy luôn Steps
    steps = fields.Nested(TestStepSchema, many=True, dump_only=True)