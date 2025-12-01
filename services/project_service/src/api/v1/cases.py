from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.extensions import db
from src.models.project import TestCase, TestSuite, ProjectMember
from src.schemas.case import TestCaseSchema
from src.utils import check_project_permission

cases_bp = Blueprint('cases', __name__)

# --- 1. TẠO TEST CASE MỚI ---
# URL: /api/v1/suites/<suite_id>/cases
@cases_bp.route('/suites/<uuid:suite_id>/cases', methods=['POST'])
@jwt_required()
def create_test_case(suite_id):
    """
    PS_13: Tạo Test Case trong Suite
    """
    current_user_id = get_jwt_identity()

    # 1. Tìm Suite để lấy Project ID
    suite = TestSuite.query.get(suite_id)
    if not suite:
        return jsonify({"error": "Suite not found"}), 404
    
    # 2. Check quyền trong Project
    _, error, code = check_project_permission(suite.project_id, current_user_id)
    if error: return error, code

    # 3. Validate Input
    data = request.get_json()
    schema = TestCaseSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # 4. Check trùng tên trong cùng Suite (BR13.1)
    if TestCase.query.filter_by(suite_id=suite_id, name=data['name']).first():
        return jsonify({"error": "Test case name already exists in this suite"}), 409

    # 5. Check Assignee (BR13.3) - Nếu có gán người
    assignee_id = data.get('assignee_user_id')
    if assignee_id:
        member = ProjectMember.query.filter_by(
            project_id=suite.project_id, 
            user_id=assignee_id
        ).first()
        if not member:
            return jsonify({"error": "Assignee is not a member of this project"}), 400

    try:
        new_case = TestCase(
            suite_id=suite_id,
            name=data['name'],
            priority=data.get('priority', 'Medium'),
            type=data.get('type', 'manual'),
            description=data.get('description'),
            assignee_user_id=assignee_id
        )
        db.session.add(new_case)
        db.session.commit()
        return jsonify(TestCaseSchema().dump(new_case)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# --- 2. XEM DANH SÁCH TEST CASE ---
# URL: /api/v1/suites/<suite_id>/cases
@cases_bp.route('/suites/<uuid:suite_id>/cases', methods=['GET'])
@jwt_required()
def list_test_cases(suite_id):
    """
    PS_16: Xem danh sách Test Case của Suite
    """
    current_user_id = get_jwt_identity()
    
    suite = TestSuite.query.get(suite_id)
    if not suite: return jsonify({"error": "Suite not found"}), 404

    _, error, code = check_project_permission(suite.project_id, current_user_id)
    if error: return error, code

    # Query
    cases = TestCase.query.filter_by(suite_id=suite_id).all()
    return jsonify(TestCaseSchema(many=True).dump(cases)), 200


# --- 3. XEM CHI TIẾT / CẬP NHẬT / XÓA ---
# Các API này thao tác trực tiếp với Case ID

@cases_bp.route('/cases/<uuid:case_id>', methods=['GET'])
@jwt_required()
def get_case_detail(case_id):
    """PS_14 (Read part)"""
    case = TestCase.query.get(case_id)
    if not case: return jsonify({"error": "Case not found"}), 404
    
    # Check quyền (truy ngược từ Case -> Suite -> Project)
    _, error, code = check_project_permission(case.suite.project_id, get_jwt_identity())
    if error: return error, code

    return jsonify(TestCaseSchema().dump(case)), 200

@cases_bp.route('/cases/<uuid:case_id>', methods=['PUT'])
@jwt_required()
def update_case(case_id):
    """PS_14: Cập nhật Test Case"""
    current_user_id = get_jwt_identity()
    case = TestCase.query.get(case_id)
    if not case: return jsonify({"error": "Case not found"}), 404

    _, error, code = check_project_permission(case.suite.project_id, current_user_id)
    if error: return error, code

    data = request.get_json()
    schema = TestCaseSchema(partial=True) # partial=True cho phép sửa lẻ tẻ
    errors = schema.validate(data)
    if errors: return jsonify(errors), 400

    # Logic update
    if 'name' in data and data['name'] != case.name:
         # Check trùng tên
        exists = TestCase.query.filter_by(suite_id=case.suite_id, name=data['name']).first()
        if exists: return jsonify({"error": "Case name exists"}), 409
        case.name = data['name']

    if 'priority' in data: case.priority = data['priority']
    if 'type' in data: case.type = data['type']
    if 'description' in data: case.description = data['description']
    
    # Check assignee valid
    if 'assignee_user_id' in data:
        assignee_id = data['assignee_user_id']
        if assignee_id: # Nếu gán người (khác None)
            member = ProjectMember.query.filter_by(project_id=case.suite.project_id, user_id=assignee_id).first()
            if not member: return jsonify({"error": "Assignee not in project"}), 400
        case.assignee_user_id = assignee_id

    try:
        db.session.commit()
        return jsonify(TestCaseSchema().dump(case)), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@cases_bp.route('/cases/<uuid:case_id>', methods=['DELETE'])
@jwt_required()
def delete_case(case_id):
    """PS_15: Xóa Test Case"""
    case = TestCase.query.get(case_id)
    if not case: return jsonify({"error": "Case not found"}), 404
    
    _, error, code = check_project_permission(case.suite.project_id, get_jwt_identity())
    if error: return error, code

    try:
        db.session.delete(case)
        db.session.commit()
        return jsonify({"message": "Case deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500