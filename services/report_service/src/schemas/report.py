from src.extensions import ma
from marshmallow import fields

class HealEventSchema(ma.Schema):
    class Meta:
        # Cập nhật fields theo đúng SQL 5.2
        fields = (
            "id", "run_id", "test_id", "project_id", 
            "page_url", "locator_old", "locator_new", 
            "engine", "chosen_source", "confidence", 
            "status", "error_message", "duration_ms", "created_at"
        )

class VisualEventSchema(ma.Schema):
    class Meta:
        # Cập nhật fields theo đúng SQL 5.3
        fields = (
            "id", "scope", "target_name", "status", "ssim_score", 
            "baseline_path", "current_path", "diff_path", "created_at"
        )

class ReportSummarySchema(ma.Schema):
    # Output run_id (UUID) thay vì id (BigInt)
    class Meta:
        fields = ("run_id", "test_id", "timestamp", "final_result", "heal_attempted", "heal_success", "total_duration_ms", "author")

class ReportDetailSchema(ma.Schema):
    # Nested schemas
    heal_events = fields.List(fields.Nested(HealEventSchema))
    visual_events = fields.List(fields.Nested(VisualEventSchema))
    
    class Meta:
        fields = (
            "run_id", "test_id", "timestamp", "final_result", 
            "heal_attempted", "heal_success", "calculated_risk",
            "app_version", "git_hash", 
            "heal_events", "visual_events"
        )