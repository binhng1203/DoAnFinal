from src.models.project import ProjectMember
from flask import jsonify
from src.extensions import db
from src.models.project import TestStep
from sqlalchemy import func

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

### NGHIỆP VỤ STEP ORDER

def get_next_step_order(case_id):
    """
    PS_17: Lấy số thứ tự tiếp theo (MAX + 1)
    """
    max_order = db.session.query(func.max(TestStep.step_order)).filter_by(case_id=case_id).scalar()
    return (max_order or 0) + 1

def shift_steps_for_insert(case_id, position):
    """
    PS_17: Dịch chuyển các bước >= position lên 1 đơn vị để chèn bước mới
    """
    TestStep.query.filter(
        TestStep.case_id == case_id,
        TestStep.step_order >= position
    ).update({TestStep.step_order: TestStep.step_order + 1}, synchronize_session=False)
    db.session.commit()

def shift_steps_after_delete(case_id, deleted_order):
    """
    PS_19: Dịch chuyển các bước > deleted_order xuống 1 đơn vị để lấp chỗ trống
    """
    TestStep.query.filter(
        TestStep.case_id == case_id,
        TestStep.step_order > deleted_order
    ).update({TestStep.step_order: TestStep.step_order - 1}, synchronize_session=False)
    db.session.commit()

def reorder_steps_update(case_id, old_order, new_order):
    """
    PS_18: Logic thay đổi vị trí phức tạp (Kéo thả)
    """
    if old_order == new_order:
        return

    if old_order < new_order:
        # TH1: Di chuyển xuống (VD: 2 -> 5)
        # Các bước từ 3,4,5 sẽ giảm đi 1 (thành 2,3,4)
        TestStep.query.filter(
            TestStep.case_id == case_id,
            TestStep.step_order > old_order,
            TestStep.step_order <= new_order
        ).update({TestStep.step_order: TestStep.step_order - 1}, synchronize_session=False)
    
    else: # old_order > new_order
        # TH2: Di chuyển lên (VD: 5 -> 2)
        # Các bước từ 2,3,4 sẽ tăng lên 1 (thành 3,4,5)
        TestStep.query.filter(
            TestStep.case_id == case_id,
            TestStep.step_order >= new_order,
            TestStep.step_order < old_order
        ).update({TestStep.step_order: TestStep.step_order + 1}, synchronize_session=False)
    
    db.session.commit()