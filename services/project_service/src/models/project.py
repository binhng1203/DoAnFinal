import uuid
import string
import secrets
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy import CheckConstraint
from src.extensions import db

# Hàm sinh ID ngẫu nhiên 8 ký tự
def generate_project_id():
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(8))


class Project(db.Model):
    __tablename__ = 'projects'
    __table_args__ = {'schema': 'management'} # [cite: 23]

    # [cite: 24] management.projects
    project_id = db.Column(db.String(8), primary_key=True, default=generate_project_id)
    name = db.Column(db.String(255), nullable=False) # BR1.1: Projectname bắt buộc
    description = db.Column(db.Text, nullable=True)
    repo_url = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(UUID(as_uuid=True), nullable=False) # Logical FK đến core.users
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    # Khi xóa Project, xóa luôn Members và Suites (Cascade) [cite: 3]
    members = db.relationship('ProjectMember', backref='project', lazy=True, cascade="all, delete-orphan")
    test_suites = db.relationship('TestSuite', backref='project', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.name}>"

class ProjectMember(db.Model):
    __tablename__ = 'project_members'
    __table_args__ = (
        # Ràng buộc CHECK cho project_role [cite: 24]
        CheckConstraint("project_role IN ('Project Admin', 'Member')", name='check_project_role_valid'),
        {'schema': 'management'}
    )

    # [cite: 24] management.project_members
    project_id = db.Column(db.String(8), db.ForeignKey('management.projects.project_id', ondelete='CASCADE'), primary_key=True)
    user_id = db.Column(UUID(as_uuid=True), primary_key=True) # Logical FK
    
    project_role = db.Column(db.String(30), nullable=False, default='Member')
    joined_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Member {self.user_id} in {self.project_id}>"

class TestSuite(db.Model):
    __tablename__ = 'test_suites'
    __table_args__ = {'schema': 'management'}

    # [cite: 24] management.test_suites
    suite_id = db.Column(db.String(255), primary_key=True)
    project_id = db.Column(db.String(8), db.ForeignKey('management.projects.project_id', ondelete='CASCADE'), nullable=False)
    
    # Self-referential FK (Thư mục cha - con)
    #[cite: 24]: parent_suite_id ON DELETE SET NULL
    parent_suite_id = db.Column(db.String(255), db.ForeignKey('management.test_suites.suite_id', ondelete='CASCADE'), nullable=True)
    
    name = db.Column(db.String(255), nullable=False)

    # Relationship để tạo cấu trúc cây (Tree View) [cite: 12]
    # 'children' giúp truy xuất các suite con từ suite cha
    children = db.relationship('TestSuite', 
                               backref=db.backref('parent', remote_side=[suite_id]),
                               lazy=True)
    
    # Khi xóa Suite, xóa luôn Test Cases bên trong (Cascade)
    test_cases = db.relationship('TestCase', backref='suite', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Suite {self.name}>"

class TestCase(db.Model):
    __tablename__ = 'test_cases'
    __table_args__ = {'schema': 'management'}

    case_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    suite_id = db.Column(db.String(255), db.ForeignKey('management.test_suites.suite_id', ondelete='CASCADE'), nullable=False)
    
    name = db.Column(db.String(255), nullable=False)
    priority = db.Column(db.String(20), default='Medium') # Low, Medium, High
    case_type = db.Column(db.String(20), default='Manual') # Manual, Automated
    description = db.Column(db.Text, nullable=True)
    
    # Metadata mới
    tags = db.Column(JSONB, default=list) # Lưu mảng các tag: ["smoke", "login"]
    assignee_id = db.Column(db.String(36), nullable=True) # User ID được assign
    is_active = db.Column(db.Boolean, default=True)
    fullscreen_page_name = db.Column(db.String(255), nullable=True)
    app_version = db.Column(db.String(50), nullable=True)
    
    # Trạng thái chạy
    last_run_status = db.Column(db.String(20), nullable=True) # PASSED, FAILED...
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = db.Column(db.String(36), nullable=True)
    updated_by = db.Column(db.String(36), nullable=True)

    # Quan hệ 1-n với TestStep (Cascade delete: Xóa case thì xóa luôn steps)
    steps = db.relationship('TestStep', backref='test_case', cascade='all, delete-orphan', order_by='TestStep.step_order')

    def __repr__(self):
        return f"<TestCase {self.name}>"
    
class TestStep(db.Model):
    __tablename__ = 'test_steps'
    __table_args__ = {'schema': 'management'}

    step_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    case_id = db.Column(db.Integer, db.ForeignKey('management.test_cases.case_id', ondelete='CASCADE'), nullable=False)
    
    step_order = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False) # Click, Type, Open...
    
    locator_type = db.Column(db.String(50), nullable=True) # XPath, CSS, ID...
    locator_value = db.Column(db.Text, nullable=True)
    
    value = db.Column(db.Text, nullable=True) # Dữ liệu nhập vào (nếu có)
    expected = db.Column(db.Text, nullable=True) # Kết quả mong đợi
    
    # URL dùng cho hành động Open URL
    url = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<TestStep {self.step_order}: {self.action}>"