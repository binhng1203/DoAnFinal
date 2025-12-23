from flask import Blueprint, request, jsonify
from sqlalchemy import Table, select, desc, or_, func
from src.extensions import db
from src.schemas.knowledge import HealingKnowledgeSchema
import logging

# Khởi tạo logger để theo dõi lỗi trong terminal backend
logger = logging.getLogger(__name__)

locators_bp = Blueprint('locators', __name__)

_healing_table = None

def get_healing_table():
    """
    Hàm helper để load bảng động (Lazy Loading).
    Sử dụng reflection để đọc cấu trúc từ Database.
    """
    global _healing_table
    if _healing_table is None:
        try:
            _healing_table = Table(
                'healing_knowledge', 
                db.metadata, 
                autoload_with=db.engine, 
                schema='public',
                extend_existing=True
            )
        except Exception as e:
            logger.error(f"Lỗi phản chiếu bảng (Table Reflection): {str(e)}")
            return None
    return _healing_table

# ----------------------------------------------------------------------
# API 1: Xem danh sách (Có phân trang và tìm kiếm)
# ----------------------------------------------------------------------
@locators_bp.route('', methods=['GET'])
def get_locators_list():
    t = get_healing_table()
    if t is None:
        return jsonify({"error": "Không thể kết nối với bảng dữ liệu"}), 500

    try:
        # 1. Lấy tham số phân trang và lọc
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 10, type=int)
        offset = (page - 1) * limit
        keyword = request.args.get('keyword')
        source_type = request.args.get('source_type')

        # 2. Xây dựng câu Query cơ bản
        stmt = select(t)

        # Lọc theo từ khóa (Search)
        if keyword:
            search = f"%{keyword}%"
            stmt = stmt.where(or_(
                t.c.old_locator_value.ilike(search),
                t.c.new_locator_value.ilike(search),
                t.c.project_id.ilike(search)
            ))
        
        # Lọc theo nguồn (Source Type)
        if source_type and source_type != 'All':
            stmt = stmt.where(t.c.source_type == source_type)

        # 3. Tính tổng số bản ghi (Cần thiết cho Frontend hiển thị số trang)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.session.execute(count_stmt).scalar()

        # 4. Sắp xếp theo updated_at và thực hiện phân trang
        stmt = stmt.order_by(desc(t.c.updated_at)) 
        stmt = stmt.limit(limit).offset(offset)

        # 5. Thực thi truy vấn
        result = db.session.execute(stmt).fetchall()

        return jsonify({
            "total": total,
            "pages": (total + limit - 1) // limit,
            "current_page": page,
            "items": HealingKnowledgeSchema(many=True).dump(result)
        }), 200

    except Exception as e:
        logger.error(f"Lỗi thực thi API danh sách: {str(e)}")
        return jsonify({"error": "Lỗi nội bộ server", "message": str(e)}), 500

# ----------------------------------------------------------------------
# API 2: Xem chi tiết một bản ghi
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# API 2: Xem chi tiết
# ----------------------------------------------------------------------
@locators_bp.route('/<int:locator_id>/history', methods=['GET'])
# @jwt_required()
def get_locator_detail(locator_id):
    # current_user_id = get_jwt_identity()
    
    t = get_healing_table()
    
    # Query: SELECT * FROM ... WHERE id = :locator_id
    stmt = select(t).where(t.c.id == locator_id)
    
    row = db.session.execute(stmt).first()
    
    if not row:
        return jsonify({"error": "Locator record not found"}), 404
        
    return jsonify(HealingKnowledgeSchema().dump(row)), 200