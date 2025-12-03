from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.extensions import db
from src.models.project import TestStep
from src.schemas.step import TestStepSchema
from src.utils import check_project_permission
from src.utils import reorder_steps_update, shift_steps_after_delete

steps_bp = Blueprint('steps', __name__)

# URL: /api/v1/steps/<step_id>
@steps_bp.route('/steps/<int:step_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def handle_step_detail(step_id):
    current_user_id = get_jwt_identity()
    
    step = TestStep.query.get(step_id)
    if not step:
        return jsonify({"error": "Test step not found"}), 404
    
    # Check quyền (Step -> Case -> Suite -> Project)
    project_id = step.test_case.suite.project_id
    _, error, code = check_project_permission(project_id, current_user_id)
    if error: return error, code

    # [PUT] Sửa Bước & Đổi Thứ Tự (PS_18)
    if request.method == 'PUT':
        data = request.get_json()
        
        # BR18.1: Action không được rỗng
        if 'action' in data and not data['action']:
            return jsonify({"error": "Action cannot be empty"}), 400

        # BR18.2: Logic đổi thứ tự
        new_order = data.get('new_order') # API nhận new_order
        if new_order and new_order != step.step_order:
            reorder_steps_update(step.case_id, step.step_order, new_order)
            step.step_order = new_order

        # Update nội dung
        if 'action' in data: step.action = data['action']
        if 'locator_type' in data: step.locator_type = data['locator_type']
        if 'locator_value' in data: step.locator_value = data['locator_value']
        if 'value' in data: step.value = data['value']
        if 'expected_result' in data: step.expected = data['expected_result'] # Map expected_result -> expected
        
        # BR18.5: Update case cha
        step.test_case.updated_by = current_user_id

        try:
            db.session.commit()
            return jsonify(TestStepSchema().dump(step)), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    # [DELETE] Xóa bước kiểm thử (PS_19)
    if request.method == 'DELETE':
        case_id = step.case_id
        deleted_order = step.step_order
        
        try:
            db.session.delete(step)
            db.session.commit() # Xóa trước
            
            # BR19.1: Logic tái cấu trúc thứ tự (lấp chỗ trống)
            shift_steps_after_delete(case_id, deleted_order)
            
            return jsonify({"message": "Step deleted and reordered"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500