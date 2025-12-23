from src.extensions import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import func

class TestRunHistory(db.Model):
    __tablename__ = 'test_run_history'
    __table_args__ = {'schema': 'custom_analytics', 'extend_existing': True}

    id = db.Column(db.BigInteger, primary_key=True)
    test_id = db.Column(db.Text, nullable=False)
    
    # [UPDATE] Thêm cột run_id (UUID string) theo SQL mới
    run_id = db.Column(db.Text, unique=True) 
    
    timestamp = db.Column(db.DateTime(timezone=True))
    raw_result = db.Column(db.Text)
    
    heal_attempted = db.Column(db.Boolean, default=False)
    heal_success = db.Column(db.Boolean, default=False)
    final_result = db.Column(db.Text, default='Running')

    calculated_risk = db.Column(db.Numeric(6, 3))

    total_duration_ms = db.Column(db.BigInteger)
    total_heal_attempts = db.Column(db.Integer, default=0)
    total_heal_success = db.Column(db.Integer, default=0)

    app_version = db.Column(db.Text)
    build_version = db.Column(db.Text)
    git_hash = db.Column(db.Text)
    author = db.Column(db.Text)
    metadata_info = db.Column("metadata", JSONB) # Map cột 'metadata'

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    # [RELATIONSHIPS]
    # Logic mới: Join giữa Parent.run_id (Text) và Child.run_id (Text)
    # Không cần cast, join trực tiếp string
    heal_events = db.relationship(
        'HealEvent',
        primaryjoin="foreign(HealEvent.run_id) == TestRunHistory.run_id",
        uselist=True,
        viewonly=True,
        lazy='select'
    )
    
    visual_events = db.relationship(
        'VisualValidationEvent',
        primaryjoin="foreign(VisualValidationEvent.run_id) == TestRunHistory.run_id",
        uselist=True,
        viewonly=True,
        lazy='select'
    )

class HealEvent(db.Model):
    __tablename__ = 'heal_event'
    __table_args__ = {'schema': 'custom_analytics', 'extend_existing': True}

    id = db.Column(db.BigInteger, primary_key=True)
    
    # [UPDATE] Đổi thành Text để khớp với SQL
    run_id = db.Column(db.Text) 
    test_id = db.Column(db.Text, nullable=False)
    project_id = db.Column(db.Text) # [UPDATE] Text

    page_url = db.Column(db.Text)
    locator_old = db.Column(db.Text, nullable=False)
    locator_new = db.Column(db.Text)
    
    engine = db.Column(db.Text, nullable=False)
    chosen_source = db.Column(db.Text)
    
    confidence = db.Column(db.Numeric(6, 3))
    risk_score = db.Column(db.Numeric(6, 3))
    threshold = db.Column(db.Numeric(6, 3))
    
    ssim_score = db.Column(db.Numeric(6, 3))
    visual_status = db.Column(db.Text)

    status = db.Column(db.Text, nullable=False)
    
    # [UPDATE] Quay lại dùng error_message và duration_ms theo SQL
    error_message = db.Column(db.Text)
    started_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    duration_ms = db.Column(db.BigInteger)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class VisualValidationEvent(db.Model):
    __tablename__ = 'visual_validation_event'
    __table_args__ = {'schema': 'custom_analytics', 'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Text)
    
    # [UPDATE] Đổi thành Text
    run_id = db.Column(db.Text) 
    
    scope = db.Column(db.Text)
    target_name = db.Column(db.Text)
    page_url = db.Column(db.Text)
    status = db.Column(db.Text)
    
    ssim_score = db.Column(db.Numeric(5, 4))
    extra_metrics = db.Column(JSONB)
    
    # [UPDATE] Dùng đuôi _path theo SQL
    baseline_path = db.Column(db.Text)
    current_path = db.Column(db.Text)
    diff_path = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())