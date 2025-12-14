from src.extensions import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import func

class TestRunHistory(db.Model):
    __tablename__ = 'test_run_history'
    __table_args__ = {'schema': 'custom_analytics', 'extend_existing': True}

    # [IMAGE] id là khóa chính, kiểu số
    id = db.Column(db.BigInteger, primary_key=True)
    test_id = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True))
    
    raw_result = db.Column(db.Text)
    heal_attempted = db.Column(db.Boolean)
    heal_success = db.Column(db.Boolean)
    final_result = db.Column(db.Text)
    
    calculated_risk = db.Column(db.Numeric) # Icon 123
    total_duration_ms = db.Column(db.BigInteger)
    total_heal_attempts = db.Column(db.Integer)
    total_heal_success = db.Column(db.Integer)
    
    app_version = db.Column(db.Text)
    build_version = db.Column(db.Text)
    git_hash = db.Column(db.Text)
    author = db.Column(db.Text)
    metadata_info = db.Column("metadata", JSONB) # Mapping cột 'metadata'
    created_at = db.Column(db.DateTime(timezone=True))

    # [RELATIONSHIPS]
    # Vì cả 2 bên đều là số (id và run_id), ta join trực tiếp không cần cast
    heal_events = db.relationship(
        'HealEvent',
        primaryjoin="foreign(HealEvent.run_id) == TestRunHistory.id",
        uselist=True,
        viewonly=True,
        lazy='select'
    )
    
    visual_events = db.relationship(
        'VisualValidationEvent',
        primaryjoin="foreign(VisualValidationEvent.run_id) == TestRunHistory.id",
        uselist=True,
        viewonly=True,
        lazy='select'
    )

class HealEvent(db.Model):
    __tablename__ = 'heal_event'
    __table_args__ = {'schema': 'custom_analytics', 'extend_existing': True}

    id = db.Column(db.BigInteger, primary_key=True)
    # [IMAGE] run_id là số (Icon 123), khớp với TestRunHistory.id
    run_id = db.Column(db.BigInteger) 
    test_id = db.Column(db.Text)
    project_id = db.Column(db.BigInteger) # Icon 123
    
    page_url = db.Column(db.Text)
    app_version = db.Column(db.Text)
    engine = db.Column(db.Text)
    
    locator_old = db.Column(db.Text)
    locator_new = db.Column(db.Text)
    chosen_source = db.Column(db.Text)
    
    confidence = db.Column(db.Numeric)
    risk_score = db.Column(db.Numeric)
    threshold = db.Column(db.Numeric)
    ssim_score = db.Column(db.Numeric)
    
    visual_status = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime(timezone=True))
    ended_at = db.Column(db.DateTime(timezone=True))
    
    # [IMAGE] Các cột mới bổ sung
    native_overhead_ms = db.Column(db.BigInteger)
    python_overhead_ms = db.Column(db.BigInteger)
    basis = db.Column(JSONB)
    
    status = db.Column(db.Text)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True))

class VisualValidationEvent(db.Model):
    __tablename__ = 'visual_validation_event'
    __table_args__ = {'schema': 'custom_analytics', 'extend_existing': True}

    id = db.Column(db.BigInteger, primary_key=True)
    test_id = db.Column(db.Text)
    run_id = db.Column(db.BigInteger) # Icon 123
    
    scope = db.Column(db.Text)
    target_name = db.Column(db.Text)
    page_url = db.Column(db.Text)
    status = db.Column(db.Text)
    
    ssim_score = db.Column(db.Numeric)
    extra_metrics = db.Column(JSONB)
    
    # [IMAGE] Sửa tên cột từ _path thành _url
    baseline_path = db.Column("baseline_url", db.Text) # Map attribute Python sang cột DB
    current_path = db.Column("current_url", db.Text)
    diff_path = db.Column("diff_url", db.Text)
    
    created_at = db.Column(db.DateTime(timezone=True))