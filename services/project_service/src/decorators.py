from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def admin_required():
    """
    Decorator để đảm bảo chỉ user có role 'Admin' mới được truy cập.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            # 1. Đảm bảo token hợp lệ
            verify_jwt_in_request()
            
            # 2. Lấy claims từ token (lúc login ta đã nhét 'roles' vào đây)
            claims = get_jwt()
            roles = claims.get("roles", [])
            
            # 3. Kiểm tra xem có role Admin không
            if "Admin" not in roles:
                return jsonify({"error": "Admin privileges required"}), 403
            
            return fn(*args, **kwargs)
        return decorator
    return wrapper