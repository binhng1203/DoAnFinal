from src.models.project import ProjectMember
from flask import jsonify

def check_project_permission(project_id, user_id, require_admin=False):
    """
    Kiểm tra xem user có thuộc project này không.
    Nếu require_admin=True, user phải là 'Project Admin'.
    Trả về: (MemberObject, ErrorResponse)
    """
    member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    
    if not member:
        return None, jsonify({"error": "You are not a member of this project"}), 403
    
    if require_admin and member.project_role != 'Project Admin':
        return None, jsonify({"error": "Project Admin privileges required"}), 403
        
    return member, None, None