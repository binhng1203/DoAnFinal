from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.extensions import db
from src.models.user import User
from src.schemas.auth import UserResponseSchema
from src.schemas.user import UserUpdateSchema

users_bp = Blueprint('users', __name__)

@users_bp.route('/me', methods=['GET'])
@jwt_required()
def get_my_profile():
    """
    US_03: Xem hồ sơ người dùng
    """
    # Lấy user_id từ Token (đã set identity lúc login)
    current_user_id = get_jwt_identity()
    
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Dùng Schema cũ của Auth để trả về (đã ẩn password)
    return jsonify(UserResponseSchema().dump(user)), 200


@users_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_my_profile():
    """
    US_04: Cập nhật hồ sơ & Đổi mật khẩu
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # 1. Validate dữ liệu đầu vào
    data = request.get_json()
    schema = UserUpdateSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # 2. Xử lý logic đổi mật khẩu (BR4.4)
    if data.get('new_password'):
        # Kiểm tra mật khẩu cũ có đúng không
        if not user.check_password(data['current_password']):
            return jsonify({"error": "Current password is incorrect"}), 400
        
        # Hash và lưu mật khẩu mới
        user.set_password(data['new_password'])

    # 3. Cập nhật thông tin cơ bản
    if 'fullname' in data:
        user.fullname = data['fullname']
    
    # BR4.2: Cập nhật username (phải check trùng)
    if 'username' in data and data['username'] != user.username:
        existing_user = User.query.filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({"error": "Username already exists"}), 409
        user.username = data['username']

    # Lưu thay đổi
    try:
        db.session.commit()
        return jsonify({
            "message": "Profile updated successfully",
            "user": UserResponseSchema().dump(user)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Error", "details": str(e)}), 500
    
@users_bp.route('/basic-info', methods=['POST'])
def get_users_basic_info():
    """
    Internal API: Lấy thông tin cơ bản cho danh sách ID
    Input: { "user_ids": ["uuid-1", "uuid-2"] }
    Output: { "uuid-1": {"fullname": "A", "email": "a@..."}, ... }
    """
    data = request.get_json()
    user_ids = data.get('user_ids', [])
    
    if not user_ids:
        return jsonify({}), 200

    # Query DB dùng hàm IN
    users = User.query.filter(User.user_id.in_(user_ids)).all()
    
    # Map kết quả thành Dictionary để dễ tra cứu
    result = {}
    for u in users:
        result[str(u.user_id)] = {
            "fullname": u.fullname
        }
        
    return jsonify(result), 200
