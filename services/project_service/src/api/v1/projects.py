from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.extensions import db
from src.models.project import Project, ProjectMember
from src.schemas.project import ProjectSchema, AddMemberSchema, MemberResponseSchema
from src.utils import check_project_permission
from sqlalchemy import and_

projects_bp = Blueprint('projects', __name__)

# --- 1. QUẢN LÝ DỰ ÁN ---

@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    """
    PS_01: Tạo dự án mới
    """
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # 1. Validate
    schema = ProjectSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    try:
        # 2. Tạo Project (BR1.1, 1.2, 1.3)
        new_project = Project(
            name=data['name'],
            description=data.get('description'),
            repo_url=data.get('repo_url'),
            created_by_user_id=current_user_id
        )
        db.session.add(new_project)
        db.session.flush() # Để lấy được project_id ngay lập tức

        # 3. Add Creator thành Admin (BR1.4)
        admin_member = ProjectMember(
            project_id=new_project.project_id,
            user_id=current_user_id,
            project_role='Project Admin'
        )
        db.session.add(admin_member)
        
        db.session.commit()

        return jsonify({
            "message": "Project created successfully",
            "project": ProjectSchema().dump(new_project)
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@projects_bp.route('', methods=['GET'])
@jwt_required()
def list_my_projects():
    """
    PS_04: Xem danh sách dự án mình tham gia
    """
    current_user_id = get_jwt_identity()
    
    # Query: Join Projects với Members để lọc theo user_id
    # BR4.1, 4.2
    results = db.session.query(Project, ProjectMember.project_role)\
        .join(ProjectMember, Project.project_id == ProjectMember.project_id)\
        .filter(ProjectMember.user_id == current_user_id)\
        .order_by(Project.created_at.desc())\
        .all()
    
    # Format lại dữ liệu trả về (kèm theo role của mình trong đó)
    projects_data = []
    for proj, role in results:
        p_dump = ProjectSchema().dump(proj)
        p_dump['my_role'] = role # BR4.3
        projects_data.append(p_dump)

    return jsonify(projects_data), 200

@projects_bp.route('/<project_id>', methods=['GET'])
@jwt_required()
def get_project_detail(project_id):
    current_user_id = get_jwt_identity()
    
    # Check quyền xem (phải là member)
    member, error, code = check_project_permission(project_id, current_user_id)
    if error: return error, code

    project = Project.query.get(project_id)
    return jsonify(ProjectSchema().dump(project)), 200


@projects_bp.route('/<project_id>', methods=['PUT'])
@jwt_required()
def update_project(project_id):
    """
    PS_02: Chỉnh sửa thông tin dự án (Chỉ Project Admin)
    """
    current_user_id = get_jwt_identity()
    
    # 1. Check quyền Admin (BR2.1)
    member, error, code = check_project_permission(project_id, current_user_id, require_admin=True)
    if error: return error, code

    # 2. Validate Input
    # Dùng partial=True để cho phép gửi lên chỉ 1 vài trường (ví dụ chỉ sửa mô tả)
    data = request.get_json()
    schema = ProjectSchema(partial=True)
    errors = schema.validate(data)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    project = Project.query.get(project_id)

    # 3. Check trùng tên (BR2.2)
    # Nếu có gửi lên name VÀ name khác name cũ -> Check DB
    if 'name' in data and data['name'] != project.name:
        existing = Project.query.filter(
            Project.name == data['name'],
            Project.project_id != project_id # Trừ chính nó ra
        ).first()
        if existing:
            return jsonify({"error": "Project name already exists"}), 409
        project.name = data['name']

    # 4. Cập nhật các trường khác
    if 'description' in data:
        project.description = data['description']
    if 'repo_url' in data:
        project.repo_url = data['repo_url']

    try:
        db.session.commit()
        return jsonify({
            "message": "Project updated successfully",
            "project": ProjectSchema().dump(project)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@projects_bp.route('/<project_id>', methods=['DELETE'])
@jwt_required()
def delete_project(project_id):
    """
    PS_03: Xóa dự án (Chỉ Project Admin)
    """
    current_user_id = get_jwt_identity()
    
    # 1. Check quyền Admin (BR3.1)
    member, error, code = check_project_permission(project_id, current_user_id, require_admin=True)
    if error: return error, code

    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # 2. Xóa (Cascade sẽ tự xóa members, suites, cases) (BR3.2)
    try:
        db.session.delete(project)
        db.session.commit()
        return jsonify({"message": "Project deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- 2. QUẢN LÝ THÀNH VIÊN (MEMBERS) ---

@projects_bp.route('/<project_id>/members', methods=['POST'])
@jwt_required()
def add_member(project_id):
    """
    PS_05: Thêm thành viên (Chỉ Project Admin)
    """
    current_user_id = get_jwt_identity()
    
    # 1. Check quyền Admin của người thực hiện (BR5.1)
    member, error, code = check_project_permission(project_id, current_user_id, require_admin=True)
    if error: return error, code

    # 2. Validate Input
    data = request.get_json()
    schema = AddMemberSchema()
    errors = schema.validate(data)
    if errors:
        return jsonify(errors), 400

    new_member_id = data['user_id']
    role = data.get('role', 'Member')

    # 3. Check user đã tồn tại trong project chưa (BR5.2)
    exists = ProjectMember.query.filter_by(project_id=project_id, user_id=new_member_id).first()
    if exists:
        return jsonify({"error": "User is already a member"}), 409

    # 4. Thêm Member (BR5.3)
    try:
        new_mem = ProjectMember(
            project_id=project_id,
            user_id=new_member_id,
            project_role=role
        )
        db.session.add(new_mem)
        db.session.commit()
        return jsonify({"message": "Member added successfully"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@projects_bp.route('/<project_id>/members', methods=['GET'])
@jwt_required()
def list_members(project_id):
    """
    PS_07: Xem danh sách thành viên
    """
    current_user_id = get_jwt_identity()
    
    # Check quyền xem
    member, error, code = check_project_permission(project_id, current_user_id)
    if error: return error, code

    # Query members
    members = ProjectMember.query.filter_by(project_id=project_id).all()
    return jsonify(MemberResponseSchema(many=True).dump(members)), 200

@projects_bp.route('/<project_id>/members/<uuid:user_id>', methods=['DELETE'])
@jwt_required()
def remove_member(project_id, user_id):
    """
    PS_06: Xóa thành viên khỏi dự án
    """
    current_requester_id = get_jwt_identity()

    # 1. Check quyền Admin của người xóa (BR6.1)
    member_admin, error, code = check_project_permission(project_id, current_requester_id, require_admin=True)
    if error: return error, code

    # 2. Không được tự xóa chính mình (BR6.2)
    if str(user_id) == str(current_requester_id):
        return jsonify({"error": "Cannot remove yourself from the project"}), 400

    # 3. Tìm thành viên cần xóa
    target_member = ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first()
    if not target_member:
        return jsonify({"error": "Member not found in this project"}), 404

    # 4. Xóa (BR6.3)
    try:
        db.session.delete(target_member)
        db.session.commit()
        return jsonify({"message": "Member removed successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@projects_bp.route('/<project_id>/join', methods=['POST'])
@jwt_required()
def join_project(project_id):
    """
    PS_08: Tham gia dự án qua ID
    """
    current_user_id = get_jwt_identity()

    # 1. Check Project tồn tại (BR8.1)
    project = Project.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # 2. Check đã là thành viên chưa (BR8.2)
    existing_member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user_id).first()
    if existing_member:
        return jsonify({"message": "You are already a member of this project"}), 200

    # 3. Thêm vào dự án với role mặc định 'Member' (BR8.3)
    try:
        new_member = ProjectMember(
            project_id=project_id,
            user_id=current_user_id,
            project_role='Member'
        )
        db.session.add(new_member)
        db.session.commit()
        
        return jsonify({
            "message": "Joined project successfully",
            "project": ProjectSchema().dump(project)
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500