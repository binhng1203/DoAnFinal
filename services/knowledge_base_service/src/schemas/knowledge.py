# src/schemas/knowledge.py
from src.extensions import ma
from marshmallow import fields

class HealingKnowledgeSchema(ma.Schema):
    # Định nghĩa các trường khớp với tên cột trong DB
    id = fields.Integer()
    project_id = fields.String()
    
    old_locator_by = fields.String()
    old_locator_value = fields.String()
    new_locator_by = fields.String()
    new_locator_value = fields.String()
    
    source_type = fields.String()
    app_version = fields.String()
    last_updated = fields.DateTime()
    
    # Các trường số liệu
    success_count = fields.Integer()
    failure_count = fields.Integer()
    avg_repair_ms = fields.Integer() # Đổi tên field này khớp với DB hoặc code xử lý
    
    commit_info = fields.Raw() # JSONB trả về nguyên dict
    
    # Field tính toán (Computed Field)
    success_rate = fields.Method("calculate_success_rate")

    def calculate_success_rate(self, obj):
        # Lưu ý: Khi dùng Reflection, 'obj' sẽ là một Row (giống Dict) hoặc KeyedTuple
        # Chúng ta truy cập bằng getattr hoặc index
        
        # Cách lấy giá trị an toàn cho cả Object và Dict/Row
        s_count = getattr(obj, 'success_count', 0)
        f_count = getattr(obj, 'failure_count', 0)
        
        # Nếu là Row object của SQLAlchemy, đôi khi phải dùng obj.success_count (nếu có key)
        # Với cách Reflection bên dưới, ta sẽ nhận được RowProxy
        
        total = s_count + f_count
        if total == 0:
            return 0
        return round((s_count / total) * 100, 2)