# self_healing/context.py
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

logger = logging.getLogger(__name__)

Locator = Tuple[str, str]
LocatorCandidate = Dict[str, Any]


@dataclass
class HealingContext:
    """
    Đối tượng mang toàn bộ thông tin cho 1 lần self-healing Python (tầng 2),
    và có thể được tái sử dụng để log thêm các sự kiện liên quan (vd: fullscreen validation).

    - driver: WebDriver hiện tại (đang trỏ qua Healenium proxy 8085).
    - broken_locator: locator gốc đã bị lỗi (by, value). Đối với một số sự kiện
      không gắn với locator cụ thể (vd: fullscreen validation), có thể truyền
      giá trị placeholder như (None, None).
    - element_name: tên logic của phần tử (hoặc tên logic trang, ví dụ "__page__:checkout_success").
    - test_context: dict chứa thông tin test (test_id, run_id, priority, commit_info, page_url, ...).

    Các field còn lại được pipeline lần lượt điền trong quá trình xử lý:
    - fingerprint, *_candidates: dữ liệu từ SuggestionLayer / HealingLayer.
    - chosen_locator, best_candidate, source_of_chosen, confidence_of_chosen:
      kết quả cuối cùng của DecisionLayer.
    - visual_validation_status, validation_scope: kết quả validation hình ảnh
      (element-level / fullscreen).
    - healing_duration_ms: thời gian thực thi pipeline (hoặc event) tính bằng ms.
    """

    driver: WebDriver
    broken_locator: Locator
    element_name: str
    test_context: Dict[str, Any] = field(default_factory=dict)

    # --- dữ liệu "dấu vân tay" và candidate của Suggestion/Healing ---
    fingerprint: Optional[Dict[str, Any]] = None
    kb_candidates: List[LocatorCandidate] = field(default_factory=list)
    hl_candidates: List[LocatorCandidate] = field(default_factory=list)
    all_candidates: List[LocatorCandidate] = field(default_factory=list)

    # --- quyết định cuối cùng & phần tử đã heal ---
    chosen_locator: Optional[Locator] = None
    best_candidate: Optional[LocatorCandidate] = None
    source_of_chosen: Optional[str] = None  # "suggestion_kb" / "heuristic" / ...
    confidence_of_chosen: Optional[float] = None
    raw_score: Optional[float] = None
    healed_element: Optional[WebElement] = None

    # --- thông tin rủi ro & quyết định ---
    risk_score: Optional[float] = None
    adaptive_threshold: Optional[float] = None
    decision_status: Optional[str] = None  # 'ACCEPTED' / 'SOFT_ACCEPT' / 'REJECTED'
    final_status: Optional[str] = None     # 'SUCCESS' / 'FAILURE' / hoặc status khác nếu dùng lại context

    # --- validation hình ảnh ---
    # element-level:  'PASSED' / 'SOFT_ACCEPT' / 'FAILED' / 'NEW_BASELINE' / 'ERROR'
    # fullscreen:     'PASSED' / 'DRIFT' / 'FAILED' / 'NEW_BASELINE' / 'ERROR'
    visual_validation_status: Optional[str] = None

    # NEW: phạm vi validation: 'ELEMENT' / 'FULLSCREEN' / None
    validation_scope: Optional[str] = None

    # --- thông tin phụ ---
    page_url: Optional[str] = None
    healing_duration_ms: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    # timer nội bộ
    _start_time: Optional[datetime] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        # Chuẩn hóa test_context
        if self.test_context is None:
            self.test_context = {}

        # Tự động lấy URL hiện tại nếu có thể
        try:
            if self.driver and not self.page_url:
                self.page_url = self.driver.current_url
        except Exception:
            pass

        # Bắt đầu đo thời gian
        self.start_timer()

    # ------------------------------------------------------------------ #
    # Timer helpers
    # ------------------------------------------------------------------ #
    def start_timer(self) -> None:
        """Bắt đầu đếm thời gian cho pipeline healing / event."""
        self._start_time = datetime.utcnow()

    def end_timer(self) -> None:
        """Kết thúc đếm thời gian và lưu lại healing_duration_ms."""
        if self._start_time is None:
            return
        delta = datetime.utcnow() - self._start_time
        self.healing_duration_ms = int(delta.total_seconds() * 1000)
        logger.info(
            f"[HealingContext] Thời gian xử lý: {self.healing_duration_ms} ms"
        )
