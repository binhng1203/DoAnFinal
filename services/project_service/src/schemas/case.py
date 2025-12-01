from src.extensions import ma
from marshmallow import fields, validate

class TestCaseSchema(ma.Schema):
    case_id = fields.UUID(dump_only=True)
    suite_id = fields.UUID(dump_only=True) # ID của suite chứa nó
    
    name = fields.String(required=True, validate=validate.Length(min=1))
    description = fields.String(allow_none=True)
    
    # Validate Enum (Khớp với DB Check Constraint)
    priority = fields.String(
        validate=validate.OneOf(["High", "Medium", "Low"]), 
        load_default="Medium"
    )
    type = fields.String(
        validate=validate.OneOf(["manual", "automated"]), 
        load_default="manual"
    )
    
    # Người được giao việc (Assignee)
    assignee_user_id = fields.UUID(allow_none=True)

class TestCaseListSchema(TestCaseSchema):
    # Schema rút gọn dùng cho danh sách (nếu cần)
    pass