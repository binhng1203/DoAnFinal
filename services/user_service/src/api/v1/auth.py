from flask import Blueprint, request, jsonify
from src.extensions import db, jwt, bcrypt
from src.models.user import User, Role
from src.schemas.auth import RegisterSchema, LoginSchema, UserResponseSchema
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError

# Tạo Blueprint (tương tự như gom nhóm URL trong Django)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    US_01: Đăng ký tài khoản
    """
    # 1. Lấy dữ liệu và Validate bằng Schema
    data = request.get_json()
    schema = RegisterSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    # 2. Kiểm tra user tồn tại (Business Rule 1.1 & 1.2)
    if User.query.filter((User.username == data['username']) | (User.email == data['email'])).first():
        return jsonify({"error": "Username or Email already exists"}), 409

    # 3. Kiểm tra Role tồn tại (Business Rule 1.5)
    role_name = data.get('role_name')
    role = Role.query.filter_by(role_name=role_name).first()
    if not role:
        return jsonify({"error": f"Role '{role_name}' not found"}), 404

    try:
        # 4. Tạo User mới
        new_user = User(
            fullname=data['fullname'],
            username=data['username'],
            email=data['email'],
            is_active=True # BR 1.6
        )
        # Hash password (BR 1.4) - Hàm này đã viết trong Models
        new_user.set_password(data['password'])

        # 5. Gán Role (BR 1.6)
        # SQLAlchemy hỗ trợ gán object trực tiếp, nó sẽ tự điền vào bảng user_roles
        new_user.roles.append(role)

        # 6. Lưu vào DB
        db.session.add(new_user)
        db.session.commit()

        # 7. Trả về kết quả
        return jsonify({
            "message": "User registered successfully",
            "user": UserResponseSchema().dump(new_user)
        }), 201

    except Exception as e:
        db.session.rollback() # Hoàn tác nếu lỗi
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    US_02: Đăng nhập
    """
    # 1. Validate input
    data = request.get_json()
    schema = LoginSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    username = data['username']
    password = data['password']

    # 2. Tìm user trong DB
    user = User.query.filter_by(username=username).first()

    # 3. Kiểm tra Password & Active (BR 2.1, 2.2, 2.3)
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not user.is_active:
        return jsonify({"error": "Account is disabled"}), 403

    # 4. Tạo JWT Token (BR 2.4, 2.5)
    # Payload mặc định chứa 'sub' (subject). Ta thêm các claim custom.
    # Lấy danh sách tên role
    role_names = [r.role_name for r in user.roles]
    
    additional_claims = {
        "user_id": str(user.user_id),
        "roles": role_names,
        "fullname": user.fullname
    }
    
    access_token = create_access_token(identity=str(user.user_id), additional_claims=additional_claims)

    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "user": UserResponseSchema().dump(user)
    }), 200