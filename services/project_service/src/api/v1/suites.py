from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.extensions import db
from src.models.project import TestSuite
from src.schemas.suite import SuiteSchema, SuiteTreeSchema
from src.utils import check_project_permission

suites_bp = Blueprint('suites', __name__)

# --- 1. TẠO TEST SUITE MỚI ---
# URL: /api/v1/projects/<project_id>/suites
@suites_bp.route('/projects/<project_id>/suites', methods=['POST'])
@jwt_required()
def create_suite(project_id):
    """
    PS_09: Tạo mới Test Suite
    """
    current_user_id = get_jwt_identity()
    
    # 1. Check quyền Member trong project (Member cũng được tạo suite)
    _, error, code = check_project_permission(project_id, current_user_id)
    if error: return error, code

    data = request.get_json()
    schema = SuiteSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # 2. Check trùng ID (Primary Key check)
    # Vì user tự nhập ID nên bắt buộc phải check xem ID này đã tồn tại chưa
    existing_id = TestSuite.query.get(data['suite_id'])
    if existing_id:
        return jsonify({"error": f"Suite ID '{data['suite_id']}' already exists"}), 409

    # 3. Validate Parent Suite (Nếu có)
    parent_id = data.get('parent_suite_id')
    if parent_id:
        parent = TestSuite.query.filter_by(suite_id=parent_id, project_id=project_id).first()
        if not parent:
            return jsonify({"error": "Parent suite not found in this project"}), 404

    # 4. Check trùng tên (Trong cùng 1 cấp cha) - BR9.1
    # Logic: Cùng cha thì không được trùng tên
    existing = TestSuite.query.filter_by(
        project_id=project_id, 
        parent_suite_id=parent_id, 
        name=data['name']
    ).first()
    if existing:
        return jsonify({"error": "Suite name already exists in this folder"}), 409

    try:
        new_suite = TestSuite(
            suite_id=data['suite_id'],
            project_id=project_id,
            name=data['name'],
            parent_suite_id=parent_id
        )
        db.session.add(new_suite)
        db.session.commit()
        return jsonify(SuiteSchema().dump(new_suite)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# --- 2. XEM CÂY THƯ MỤC (TREE VIEW) ---
# URL: /api/v1/projects/<project_id>/suites
@suites_bp.route('/projects/<project_id>/suites', methods=['GET'])
@jwt_required()
def get_suite_tree(project_id):
    """
    PS_12: Lấy cây thư mục Test Suite
    """
    current_user_id = get_jwt_identity()
    _, error, code = check_project_permission(project_id, current_user_id)
    if error: return error, code

    # 1. Lấy tất cả suite gốc (parent_id = None)
    # Nhờ relationship 'children' trong Model và Schema đệ quy,
    # nó sẽ tự động load hết các cấp con cháu.
    root_suites = TestSuite.query.filter_by(project_id=project_id, parent_suite_id=None).all()
    
    return jsonify(SuiteTreeSchema(many=True).dump(root_suites)), 200


# --- 3. CẬP NHẬT TEST SUITE ---
# URL: /api/v1/suites/<suite_id>
@suites_bp.route('/suites/<string:suite_id>', methods=['PUT'])
@jwt_required()
def update_suite(suite_id):
    """
    PS_10: Chỉnh sửa / Di chuyển Suite
    """
    current_user_id = get_jwt_identity()
    
    suite = TestSuite.query.get(suite_id)
    if not suite:
        return jsonify({"error": "Suite not found"}), 404
        
    # Check quyền trong project chứa suite này
    _, error, code = check_project_permission(suite.project_id, current_user_id)
    if error: return error, code

    data = request.get_json()
    
    # 1. Logic đổi tên
    if 'name' in data and data['name'] != suite.name:
        # Check trùng tên ở folder hiện tại
        exists = TestSuite.query.filter_by(
            project_id=suite.project_id,
            parent_suite_id=suite.parent_suite_id,
            name=data['name']
        ).first()
        if exists: return jsonify({"error": "Suite name exists"}), 409
        suite.name = data['name']

    # 2. Logic di chuyển (Đổi cha)
    if 'parent_suite_id' in data:
        new_parent_id = data['parent_suite_id']
        
        # BR10.2: Không được chọn chính nó làm cha
        if str(new_parent_id) == str(suite_id):
            return jsonify({"error": "Cannot move suite into itself"}), 400
            
        # NÂNG CAO: Check không được chuyển vào con cháu của chính mình (Vòng lặp)
        # (Tạm thời bỏ qua nếu logic phức tạp, nhưng nên làm)
        if new_parent_id:
            new_parent = TestSuite.query.get(new_parent_id)
            # Nếu new_parent không tồn tại hoặc khác project
            if not new_parent or new_parent.project_id != suite.project_id:
                return jsonify({"error": "Invalid parent suite"}), 400
                
        suite.parent_suite_id = new_parent_id

    try:
        db.session.commit()
        return jsonify(SuiteSchema().dump(suite)), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# --- 4. XÓA TEST SUITE ---
# URL: /api/v1/suites/<suite_id>
@suites_bp.route('/suites/<string:suite_id>', methods=['DELETE'])
@jwt_required()
def delete_suite(suite_id):
    """
    PS_11: Xóa Test Suite (Cascade xóa con + test cases)
    """
    current_user_id = get_jwt_identity()
    
    suite = TestSuite.query.get(suite_id)
    if not suite:
        return jsonify({"error": "Suite not found"}), 404
        
    _, error, code = check_project_permission(suite.project_id, current_user_id)
    if error: return error, code

    try:
        db.session.delete(suite)
        db.session.commit()
        return jsonify({"message": "Suite deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500