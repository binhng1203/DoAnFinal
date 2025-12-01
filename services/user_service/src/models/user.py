import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.extensions import db, bcrypt

# --- BẢNG TRUNG GIAN (Association Tables) ---
# Trong Django bạn phải khai báo Class, nhưng trong SQLAlchemy 
# dùng bảng phụ (db.Table) gọn hơn cho quan hệ Many-to-Many.

user_roles = db.Table(
    'user_roles',
    db.metadata,
    db.Column('user_id', UUID(as_uuid=True), db.ForeignKey('core.users.user_id', ondelete='CASCADE'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('core.roles.role_id', ondelete='CASCADE'), primary_key=True),
    schema='core'  # QUAN TRỌNG: Định nghĩa schema
)

role_permissions = db.Table(
    'role_permissions',
    db.metadata,
    db.Column('role_id', db.Integer, db.ForeignKey('core.roles.role_id', ondelete='CASCADE'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('core.permissions.permission_id', ondelete='CASCADE'), primary_key=True),
    schema='core'  # QUAN TRỌNG
)

# --- MODELS CHÍNH ---

class Permission(db.Model):
    __tablename__ = 'permissions'
    __table_args__ = {'schema': 'core'} # Bắt buộc phải có dòng này

    permission_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    permission_key = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Permission {self.permission_key}>"

class Role(db.Model):
    __tablename__ = 'roles'
    __table_args__ = {'schema': 'core'}

    role_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Quan hệ với Permission (Many-to-Many)
    permissions = db.relationship(
        'Permission',
        secondary=role_permissions,
        lazy='subquery',
        backref=db.backref('roles', lazy=True)
    )

    def __repr__(self):
        return f"<Role {self.role_name}>"

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'core'}

    user_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fullname = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Quan hệ với Role (Many-to-Many)
    # User.roles sẽ trả về list các object Role
    roles = db.relationship(
        'Role',
        secondary=user_roles,
        lazy='subquery',
        backref=db.backref('users', lazy=True)
    )

    # Hàm tiện ích để hash password
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    # Hàm tiện ích để kiểm tra password
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"