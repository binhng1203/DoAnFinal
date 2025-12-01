import uuid
import string
import secrets
from sqlalchemy.dialects.postgresql import UUID
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
    suite_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(db.String(8), db.ForeignKey('management.projects.project_id', ondelete='CASCADE'), nullable=False)
    
    # Self-referential FK (Thư mục cha - con)
    #[cite: 24]: parent_suite_id ON DELETE SET NULL
    parent_suite_id = db.Column(UUID(as_uuid=True), db.ForeignKey('management.test_suites.suite_id', ondelete='SET NULL'), nullable=True)
    
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
    __table_args__ = (
        # Ràng buộc CHECK cho priority và type [cite: 24]
        CheckConstraint("priority IN ('High', 'Medium', 'Low')", name='check_priority_valid'),
        CheckConstraint("type IN ('manual', 'automated')", name='check_type_valid'),
        {'schema': 'management'}
    )

    # [cite: 24] management.test_cases
    case_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suite_id = db.Column(UUID(as_uuid=True), db.ForeignKey('management.test_suites.suite_id', ondelete='CASCADE'), nullable=False)
    
    name = db.Column(db.String(255), nullable=False)
    priority = db.Column(db.String(20), default='Medium')
    type = db.Column(db.String(20), default='manual')
    description = db.Column(db.Text, nullable=True)
    assignee_user_id = db.Column(UUID(as_uuid=True), nullable=True) # Logical FK

    def __repr__(self):
        return f"<TestCase {self.name}>"