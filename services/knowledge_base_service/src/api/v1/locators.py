from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import Table, select, desc, or_
from src.extensions import db
from src.schemas.knowledge import HealingKnowledgeSchema

locators_bp = Blueprint('locators', __name__)

# Biến global để lưu bảng sau khi reflect (tránh reflect lại nhiều lần)
_healing_table = None

def get_healing_table():
    """
    Hàm helper để load bảng động (Lazy Loading).
    Chỉ reflect DB khi cần dùng đến lần đầu tiên.
    """
    global _healing_table
    if _healing_table is None:
        # Tự động đọc cấu trúc bảng 'healing_knowledge' từ schema 'public'
        _healing_table = Table(
            'healing_knowledge', 
            db.metadata, 
            autoload_with=db.engine, 
            schema='public',
            extend_existing=True
        )
    return _healing_table

# ----------------------------------------------------------------------
# API 1: Xem danh sách
# ----------------------------------------------------------------------
@locators_bp.route('', methods=['GET'])
@jwt_required()
def get_locators_list():
    current_user_id = get_jwt_identity()

    # 1. Load bảng
    t = get_healing_table()

    # 2. Chuẩn bị query params
    keyword = request.args.get('keyword')
    source_type = request.args.get('source_type')
    app_version = request.args.get('app_version')
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    offset = (page - 1) * limit

    # 3. Xây dựng câu Query (Dùng SQLAlchemy Core)
    # select(t) tương đương SELECT * FROM public.healing_knowledge
    stmt = select(t)

    # Filter
    if keyword:
        search = f"%{keyword}%"
        stmt = stmt.where(or_(
            t.c.old_locator_value.ilike(search),
            t.c.new_locator_value.ilike(search),
            t.c.project_id.ilike(search)
        ))
    
    if source_type:
        stmt = stmt.where(t.c.source_type == source_type)
        
    if app_version:
        stmt = stmt.where(t.c.app_version == app_version)

    # Sort & Pagination
    # Đếm tổng số bản ghi (query riêng để tối ưu)
    count_stmt = select(db.func.count()).select_from(stmt.subquery())
    total = db.session.execute(count_stmt).scalar()

    # Thêm sort và limit vào câu query chính
    stmt = stmt.order_by(desc(t.c.last_updated))
    stmt = stmt.limit(limit).offset(offset)

    # 4. Thực thi
    result = db.session.execute(stmt).fetchall()

    # 5. Trả về
    return jsonify({
        "total": total,
        "pages": (total + limit - 1) // limit,
        "current_page": page,
        # Dump dữ liệu Row vào Schema
        "items": HealingKnowledgeSchema(many=True).dump(result)
    }), 200


# ----------------------------------------------------------------------
# API 2: Xem chi tiết
# ----------------------------------------------------------------------
@locators_bp.route('/<int:locator_id>/history', methods=['GET'])
@jwt_required()
def get_locator_detail(locator_id):
    current_user_id = get_jwt_identity()
    
    t = get_healing_table()
    
    # Query: SELECT * FROM ... WHERE id = :locator_id
    stmt = select(t).where(t.c.id == locator_id)
    
    row = db.session.execute(stmt).first()
    
    if not row:
        return jsonify({"error": "Locator record not found"}), 404
        
    return jsonify(HealingKnowledgeSchema().dump(row)), 200