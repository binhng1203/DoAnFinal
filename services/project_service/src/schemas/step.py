from src.extensions import ma
from marshmallow import fields, validate

class TestStepSchema(ma.Schema):
    step_id = fields.Integer(dump_only=True)
    case_id = fields.Integer(dump_only=True)
    
    # Validate Action không được rỗng
    action = fields.String(required=True, validate=validate.Length(min=1))
    
    step_order = fields.Integer() # Có thể null (backend tự tính)
    
    locator_type = fields.String(allow_none=True)
    locator_value = fields.String(allow_none=True)
    value = fields.String(allow_none=True)
    expected = fields.String(allow_none=True)
    url = fields.String(allow_none=True)