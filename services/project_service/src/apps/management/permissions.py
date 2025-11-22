from rest_framework import permissions
from .models import Project, TestSuite, TestCase, ProjectMember

class IsProjectAdmin(permissions.BasePermission):
    """
    Chỉ cho phép nếu user là 'Project Admin' của dự án.
    """
    def has_object_permission(self, request, view, obj):
        # 1. Tìm ra Project cha của object hiện tại
        project = _get_project_from_object(obj)
        
        if not project:
            return False

        # 2. Kiểm tra quyền Admin
        return ProjectMember.objects.filter(
            project=project,
            user_id=request.user.user_id,
            project_role=ProjectMember.Role.ADMIN
        ).exists()

class IsProjectMember(permissions.BasePermission):
    """
    Cho phép truy cập nếu user là thành viên (bất kể role).
    """
    def has_object_permission(self, request, view, obj):
        # 1. Tìm ra Project cha của object hiện tại
        project = _get_project_from_object(obj)

        if not project:
            return False

        # 2. Kiểm tra user có trong danh sách thành viên không
        return ProjectMember.objects.filter(
            project=project,
            user_id=request.user.user_id
        ).exists()

# --- Helper Function (Hàm phụ trợ) ---
def _get_project_from_object(obj):
    """
    Hàm này giúp tìm Project instance từ các object khác nhau
    (Project, TestSuite, TestCase).
    """
    # Trường hợp 1: Object chính là Project
    if isinstance(obj, Project):
        return obj
    
    # Trường hợp 2: Object là TestSuite (có FK 'project')
    if isinstance(obj, TestSuite):
        return obj.project
        
    # Trường hợp 3: Object là TestCase (TestCase -> Suite -> Project)
    if isinstance(obj, TestCase):
        return obj.suite.project
        
    # Trường hợp dự phòng: Nếu object có thuộc tính 'project'
    if hasattr(obj, 'project'):
        return obj.project

    return None