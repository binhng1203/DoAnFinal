from flask import Blueprint, jsonify, request
from src.extensions import db
from src.models.user import User, Role, Permission
from src.schemas.auth import UserResponseSchema
from src.schemas.admin import RoleSchema, PermissionSchema, AssignRoleSchema
from src.decorators import admin_required

admin_bp = Blueprint('admin', __name__)

# --- QUẢN LÝ USER ---

@admin_bp.route('/users', methods=['GET'])
@admin_required()
def get_all_users():
    """
    Lấy danh sách tất cả user trong hệ thống
    """
    users = User.query.order_by(User.created_at.desc()).all()
    # Dùng many=True để dump danh sách
    return jsonify(UserResponseSchema(many=True).dump(users)), 200

@admin_bp.route('/users/<uuid:user_id>/roles', methods=['POST'])
@admin_required()
def assign_role_to_user(user_id):
    """
    Gán thêm Role cho User
    """
    # 1. Tìm User
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # 2. Validate role_id gửi lên
    data = request.get_json()
    schema = AssignRoleSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # 3. Tìm Role
    role_id = data['role_id']
    role = Role.query.get(role_id)
    new_role = Role.query.get(role_id)
    if not new_role:
        return jsonify({"error": "Role not found"}), 404

    # 4. Gán Role (LOGIC MỚI)
    try:
        # --- MỚI (ĐÚNG yêu cầu): Gán đè danh sách ---
        # SQLAlchemy sẽ tự động xóa các dòng user_roles cũ và insert dòng mới
        user.roles = [new_role] 
        
        db.session.commit()
        
        return jsonify({
            "message": f"User '{user.username}' is now assigned to role '{new_role.role_name}'",
            # Trả về list để client thấy rõ chỉ còn 1 role
            "current_roles": [r.role_name for r in user.roles] 
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

# --- QUẢN LÝ ROLES & PERMISSIONS ---

@admin_bp.route('/roles', methods=['GET'])
@admin_required()
def get_all_roles():
    roles = Role.query.all()
    return jsonify(RoleSchema(many=True).dump(roles)), 200

@admin_bp.route('/permissions', methods=['GET'])
@admin_required()
def get_all_permissions():
    perms = Permission.query.all()
    return jsonify(PermissionSchema(many=True).dump(perms)), 200