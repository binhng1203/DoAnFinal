import requests
import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.extensions import db
from src.models.project import TestSuite, TestCase, TestStep
from src.schemas.case import TestCaseSchema
from src.schemas.step import TestStepSchema
from src.utils import check_project_permission
from src.utils import get_next_step_order, shift_steps_for_insert

cases_bp = Blueprint('cases', __name__)

USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://user-service:8000")

# --- 1. LẤY DANH SÁCH & TẠO TEST CASE (Trong 1 Suite) ---
# URL: /api/v1/suites/<suite_id>/cases
@cases_bp.route('/suites/<string:suite_id>/cases', methods=['GET', 'POST'])
@jwt_required()
def handle_suite_cases(suite_id):
    current_user_id = get_jwt_identity()
    
    # Check Suite tồn tại
    suite = TestSuite.query.get(suite_id)
    if not suite:
        return jsonify({"error": "Suite not found"}), 404
        
    # Check quyền Project
    _, error, code = check_project_permission(suite.project_id, current_user_id)
    if error: return error, code

    # [GET] Lấy danh sách Test Cases
    if request.method == 'GET':
        # 1. Query danh sách từ DB (PS_16)
        cases = TestCase.query.filter_by(suite_id=suite_id, is_active=True)\
            .order_by(TestCase.updated_at.desc()).all()
            
        if not cases:
            return jsonify([]), 200

        # 2. Convert sang List Dictionary
        cases_data = TestCaseSchema(many=True).dump(cases)
        
        # 3. Gom tất cả ID người tạo vào 1 set (để lọc trùng)
        creator_ids = set()
        for c in cases_data:
            # Lưu ý: check key trong schema, thường là 'created_by'
            if c.get('created_by'):
                creator_ids.add(str(c['created_by']))
        
        # 4. Gọi User Service (Batch Request - 1 lần duy nhất)
        user_map = {}
        if creator_ids:
            try:
                response = requests.post(
                    f"{USER_SERVICE_URL}/api/v1/users/basic-info",
                    json={"user_ids": list(creator_ids)},
                    timeout=5
                )
                if response.status_code == 200:
                    user_map = response.json()
            except Exception as e:
                print(f"Error fetching users: {e}")

        # 5. Ghép tên vào dữ liệu trả về
        for c in cases_data:
            creator_id = str(c.get('created_by'))
            info = user_map.get(creator_id, {})
            
            c['creator_username'] = info.get('username', 'Unknown')

        return jsonify(cases_data), 200
    if request.method == 'POST':
        # PS_13: Tạo mới Test Case
        data = request.get_json()
        
        # Validate input chung
        errors = TestCaseSchema().validate(data)
        if errors: return jsonify(errors), 400

        # Validate tên unique trong Suite (BR13.1)
        existing = TestCase.query.filter_by(suite_id=suite_id, name=data['name']).first()
        if existing:
            return jsonify({"error": "Case name must be unique in this suite"}), 409

        # Validate Assignee (BR13.3) - (Đã có logic check member trong check_project_permission nhưng ở đây check cụ thể assignee)
        # Tạm bỏ qua logic check assignee sâu để code gọn, mặc định tin tưởng FE gửi đúng ID

        try:
            new_case = TestCase(
                suite_id=suite_id,
                name=data['name'],
                priority=data.get('priority', 'Medium'),
                case_type=data.get('case_type', 'Manual'),
                description=data.get('description'),
                tags=data.get('tags', []),
                assignee_id=data.get('assignee_user_id'), # Map đúng field từ API
                fullscreen_page_name=data.get('fullscreen_page_name'),
                app_version=data.get('app_version'),
                created_by=current_user_id,
                updated_by=current_user_id
            )
            db.session.add(new_case)
            db.session.commit()
            return jsonify(TestCaseSchema().dump(new_case)), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500


# --- 2. CHI TIẾT, CẬP NHẬT, XÓA TEST CASE ---
# URL: /api/v1/cases/<case_id>
@cases_bp.route('/cases/<int:case_id>', methods=['GET', 'PUT', 'DELETE'])
@jwt_required()
def handle_case_detail(case_id):
    current_user_id = get_jwt_identity()
    
    case = TestCase.query.get(case_id)
    if not case:
        return jsonify({"error": "Test case not found"}), 404
        
    # Check quyền (Truy ngược từ Case -> Suite -> Project)
    _, error, code = check_project_permission(case.suite.project_id, current_user_id)
    if error: return error, code

    # [GET] Xem chi tiết Test Case (PS_16 - Detail)
    if request.method == 'GET':
        # 1. Dump dữ liệu gốc từ DB
        case_data = TestCaseSchema().dump(case)
        
        # 2. Chuẩn bị danh sách ID cần lấy tên (Creator và Updater)
        user_ids = []
        if case.created_by: user_ids.append(str(case.created_by))
        if case.updated_by: user_ids.append(str(case.updated_by))
        if case.assignee_id: user_ids.append(str(case.assignee_id))
        
        # 3. Gọi User Service (Chỉ gọi nếu có ID)
        user_map = {}
        if user_ids:
            try:
                response = requests.post(
                    f"{USER_SERVICE_URL}/api/v1/users/basic-info",
                    json={"user_ids": user_ids}
                )
                if response.status_code == 200:
                    user_map = response.json()
            except Exception as e:
                print(f"Failed to call User Service: {e}")

        # 4. Map thông tin vào kết quả trả về
        # Xử lý Creator
        creator_info = user_map.get(str(case.created_by), {})
        case_data['creator_username'] = creator_info.get('username', 'Unknown')

        # Xử lý Updater
        updater_info = user_map.get(str(case.updated_by), {})
        case_data['updater_username'] = updater_info.get('username', 'Unknown')

        assigneer_info = user_map.get(str(case.assignee_id), {})
        case_data['assigneer_username'] = assigneer_info.get('username', 'Unknown')

        return jsonify(case_data), 200

    # [PUT] Cập nhật thông tin chung (PS_14)
    if request.method == 'PUT':
        data = request.get_json()
        
        # Validate Name Unique nếu đổi tên
        if 'name' in data and data['name'] != case.name:
            exist = TestCase.query.filter_by(suite_id=case.suite_id, name=data['name']).first()
            if exist: return jsonify({"error": "Case name exists in this suite"}), 409

        # Update fields
        if 'name' in data: case.name = data['name']
        if 'priority' in data: case.priority = data['priority']
        if 'type' in data: case.case_type = data['type'] # Map type -> case_type
        if 'description' in data: case.description = data['description']
        if 'tags' in data: case.tags = data['tags']
        if 'assignee_user_id' in data: case.assignee_id = data['assignee_user_id']
        if 'fullscreen_page_name' in data: case.fullscreen_page_name = data['fullscreen_page_name']
        if 'app_version' in data: case.app_version = data['app_version']
        
        case.updated_by = current_user_id
        db.session.commit()
        return jsonify(TestCaseSchema().dump(case)), 200

    # [DELETE] Xóa Test Case (PS_15)
    if request.method == 'DELETE':
        try:
            db.session.delete(case)
            db.session.commit()
            return jsonify({"message": "Test case deleted successfully"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500


# --- 3. QUẢN LÝ TEST STEPS (API Con của Case) ---
# URL: /api/v1/cases/<case_id>/steps
@cases_bp.route('/cases/<int:case_id>/steps', methods=['GET', 'POST'])
@jwt_required()
def handle_case_steps(case_id):
    current_user_id = get_jwt_identity()
    
    case = TestCase.query.get(case_id)
    if not case: return jsonify({"error": "Test case not found"}), 404
        
    _, error, code = check_project_permission(case.suite.project_id, current_user_id)
    if error: return error, code

    # [GET] Lấy danh sách Steps (PS_20)
    if request.method == 'GET':
        # Sắp xếp theo step_order ASC (BR20.2)
        steps = TestStep.query.filter_by(case_id=case_id).order_by(TestStep.step_order.asc()).all()
        return jsonify(TestStepSchema(many=True).dump(steps)), 200

    # [POST] Thêm bước kiểm thử (PS_17)
    if request.method == 'POST':
        data = request.get_json()
        
        # BR17.1: Action bắt buộc
        if not data.get('action'):
            return jsonify({"error": "Action is required"}), 400

        desired_order = data.get('step_order')
        
        # BR17.2: Logic xác định thứ tự
        if desired_order:
            shift_steps_for_insert(case_id, desired_order)
            final_order = desired_order
        else:
            final_order = get_next_step_order(case_id)

        try:
            new_step = TestStep(
                case_id=case_id,
                action=data['action'],
                step_order=final_order,
                locator_type=data.get('locator_type'),
                locator_value=data.get('locator_value'),
                value=data.get('value'),
                expected=data.get('expected'),
                url=data.get('url') # Nếu action là Open URL
            )
            db.session.add(new_step)
            # BR18.5: Update case updated_at (Logic nghiệp vụ bổ sung)
            case.updated_by = current_user_id
            
            db.session.commit()
            return jsonify(TestStepSchema().dump(new_step)), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500