from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, List

@dataclass
class HealingContext:
    """
    Context object to hold state during the healing process.
    All fields are optional to allow initialization at the start of the test.
    """
    # Các tham số cơ bản (cho phép None)
    driver: Any = None
    broken_locator: Optional[Tuple[str, str]] = None
    element_name: Optional[str] = None
    
    # Thông tin về Test Run
    test_context: Dict[str, Any] = field(default_factory=dict)
    
    # Trạng thái Healing
    healing_started_at: Optional[Any] = None
    healing_duration_ms: int = 0
    
    # Kết quả tìm kiếm
    candidates: List[Any] = field(default_factory=list)
    best_candidate: Optional[Dict[str, Any]] = None
    chosen_locator: Optional[Tuple[str, str]] = None
    confidence_of_chosen: float = 0.0
    
    # Engine & Status
    engine_used: str = "PYTHON"
    final_status: str = "SKIPPED"  # SUCCESS, FAILURE, SKIPPED
    
    # Visual Validation
    last_ssim_score: Optional[float] = None
    visual_validation_status: Optional[str] = None
    
    # Data bổ trợ
    page_url: str = ""
    page_source: str = ""
    fingerprint: Optional[Dict[str, Any]] = None
    basis_json: Dict[str, Any] = field(default_factory=dict)
    
    # Metrics
    native_overhead_ms: int = 0
    python_overhead_ms: int = 0
    risk_score: float = 0.0
    adaptive_threshold: float = 0.0

    def __post_init__(self):
        # Đảm bảo test_context luôn là dict nếu người dùng lỡ truyền None
        if self.test_context is None:
            self.test_context = {}