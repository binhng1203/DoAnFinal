from src.extensions import ma
from marshmallow import fields, validate

# Schema validate khi Tạo/Sửa Suite
class SuiteSchema(ma.Schema):
    suite_id = fields.String(required=True, validate=validate.Length(min=1, max=255))
    project_id = fields.String(dump_only=True)
    
    name = fields.String(required=True, validate=validate.Length(min=1))
    parent_suite_id = fields.String(allow_none=True)
    
    # Số lượng test case bên trong (Optional - để hiển thị cho đẹp)
    test_case_count = fields.Integer(dump_only=True)

# Schema ĐỆ QUY để trả về cấu trúc cây (Tree View)
class SuiteTreeSchema(ma.Schema):
    suite_id = fields.UUID()
    name = fields.String()
    parent_suite_id = fields.UUID()
    
    # Đây là phép thuật: Field này tự gọi lại chính Schema này để lấy danh sách con
    children = fields.List(fields.Nested(lambda: SuiteTreeSchema()))