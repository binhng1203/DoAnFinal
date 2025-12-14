from src.extensions import ma
from marshmallow import fields

class HealEventSchema(ma.Schema):
    class Meta:
        # Thêm các trường mới
        fields = ("id", "locator_old", "locator_new", "status", "confidence", "engine", "reason", "basis", "created_at")

class VisualEventSchema(ma.Schema):
    # Mapping lại tên cột cho đẹp
    baseline_url = fields.String(attribute="baseline_path")
    current_url = fields.String(attribute="current_path")
    diff_url = fields.String(attribute="diff_path")
    
    class Meta:
        fields = ("id", "scope", "target_name", "status", "ssim_score", "baseline_url", "current_url", "diff_url")

class ReportSummarySchema(ma.Schema):
    # Map id -> run_id
    run_id = fields.String(attribute="id")
    class Meta:
        fields = ("run_id", "test_id", "timestamp", "final_result", "heal_attempted", "heal_success", "total_duration_ms", "author")

class ReportDetailSchema(ma.Schema):
    run_id = fields.String(attribute="id")
    heal_events = fields.List(fields.Nested(HealEventSchema))
    visual_events = fields.List(fields.Nested(VisualEventSchema))
    
    class Meta:
        fields = ("run_id", "test_id", "timestamp", "final_result", "heal_attempted", "heal_success", 
                  "app_version", "git_hash", "heal_events", "visual_events")