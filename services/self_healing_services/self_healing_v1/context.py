import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

@dataclass
class HealingContext:
    # --- Global Context (Thông tin chung của Test Run) ---
    test_context: Dict[str, Any] = field(default_factory=dict)
    raw_result: str = "N/A"
    # --- Element Context (Thông tin riêng cho từng lần tìm Element) ---
    element_name: Optional[str] = None
    broken_locator: Optional[Tuple[str, str]] = None
    chosen_locator: Optional[Tuple[str, str]] = None
    
    # --- Healing Details (Chi tiết quá trình) ---
    page_url: str = ""
    fingerprint: Optional[str] = None
    all_candidates: List[str] = field(default_factory=list)
    kb_candidates: List[Dict] = field(default_factory=list)
    
    # --- Decision Metrics (Các chỉ số quyết định) ---
    decision_status: str = "PENDING"  # APPROVED, REJECTED, PENDING
    source_of_chosen: str = "NONE"    # KB, HEALENIUM, LLM...
    raw_score: float = 0.0
    risk_score: float = 0.0
    adaptive_threshold: float = 0.0
    
    # --- Visual Validation ---
    visual_validation_status: str = "N/A" # PASS, FAIL, N/A
    last_ssim_score: float = 0.0
    
    # --- Final Result ---
    final_status: str = "SKIPPED"     # SKIPPED (nếu native tìm thấy), SUCCESS, FAILURE
    
    # --- Timers ---
    _start_ts: float = 0.0
    healing_duration_ms: int = 0

    def reset_element_context(self, element_name: Optional[str] = None):
        """
        [FIX] Hàm này giúp reset trạng thái để tránh dùng nhầm dữ liệu của element cũ.
        """
        self.raw_result = "N/A"
        self.element_name = element_name
        self.broken_locator = None
        self.chosen_locator = None
        self.page_url = ""
        self.fingerprint = None
        self.all_candidates = []
        self.kb_candidates = []
        
        self.decision_status = "PENDING"
        self.source_of_chosen = "NONE"
        self.raw_score = 0.0
        self.risk_score = 0.0
        
        self.visual_validation_status = "N/A"
        self.final_status = "SKIPPED"
        
        self._start_ts = 0.0
        self.healing_duration_ms = 0

    def start_timer(self):
        self._start_ts = time.perf_counter()

    def end_timer(self):
        if self._start_ts > 0:
            self.healing_duration_ms = int((time.perf_counter() - self._start_ts) * 1000)

    def elapsed_ms(self) -> int:
        if self._start_ts > 0:
            return int((time.perf_counter() - self._start_ts) * 1000)
        return 0