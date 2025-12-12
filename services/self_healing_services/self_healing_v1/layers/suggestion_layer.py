# self_healing_v1/layers/suggestion_layer.py

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

from ..utils.element_fingerprint import ElementFingerprint
from ..services.cloud_kb_client import CloudKnowledgeBaseClient

logger = logging.getLogger(__name__)

class SuggestionLayer:
    """
    Layer 1: Suggestion
    Nhiệm vụ: Tra cứu nhanh từ Knowledge Base (Cache/History).
    Nếu tìm thấy gợi ý, verify nhanh trên DOM. Nếu tồn tại thì trả về ngay.
    Nếu không tìm thấy hoặc gợi ý không còn đúng, trả về None để chuyển sang Layer 2.
    """

    # Mapping từ string trong DB sang đối tượng By của Selenium
    STRATEGY_MAP = {
        "id": By.ID,
        "xpath": By.XPATH,
        "link text": By.LINK_TEXT,
        "partial link text": By.PARTIAL_LINK_TEXT,
        "name": By.NAME,
        "tag name": By.TAG_NAME,
        "class name": By.CLASS_NAME,
        "css selector": By.CSS_SELECTOR,
        "css": By.CSS_SELECTOR # Alias
    }

    def __init__(self, cloud_kb_client: CloudKnowledgeBaseClient):
        self.cloud_kb_client = cloud_kb_client
        self.last_fingerprint: Optional[Dict[str, Any]] = None

    def get_suggestions(
        self,
        broken_locator: Tuple[str, str],
        driver: WebDriver,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Lấy candidate từ KB dựa trên 'chữ ký' của locator hỏng.
        
        Args:
            broken_locator: Tuple (By, Value) ví dụ (By.ID, "submit_btn")
            driver: WebDriver instance (chỉ dùng để lấy URL và verify candidate)
        """
        
        # 1. Tạo Fingerprint (Static Analysis)
        # Chúng ta phân tích chuỗi selector của locator hỏng để tạo key tra cứu.
        # Không tương tác với DOM ở bước này.
        logger.info(f"[SuggestionLayer] Tạo fingerprint từ locator hỏng: {broken_locator}")
        
        fingerprint_generator = ElementFingerprint(broken_locator)
        self.last_fingerprint = fingerprint_generator.get()

        if not self.last_fingerprint:
            logger.warning("[SuggestionLayer] Không thể tạo fingerprint. Bỏ qua Layer 1.")
            return None

        # 2. Truy vấn Knowledge Base
        page_url = driver.current_url if driver.current_url else "unknown"
        logger.info("[SuggestionLayer] Truy vấn Healing Knowledge Base...")
        
        suggestions = self.cloud_kb_client.get_suggestions(
            fingerprint=self.last_fingerprint,
            page_url=page_url
        )

        # Chuẩn hóa dữ liệu về dạng List
        candidate_list = []
        if isinstance(suggestions, list):
            candidate_list = suggestions
        elif isinstance(suggestions, dict):
            candidate_list = [suggestions]
        
        if not candidate_list:
            logger.info("[SuggestionLayer] KB không có dữ liệu cho fingerprint này.")
            return None

        # 3. Quick Validation (Kiểm tra tồn tại)
        # Lọc bỏ các gợi ý từ quá khứ nhưng hiện tại không còn xuất hiện trên màn hình
        valid_candidates = []
        
        for candidate in candidate_list:
            # Giả định cấu trúc candidate từ KB: {'type': 'xpath', 'value': '//div[@id="new"]', 'score': 0.9}
            strategy_str = candidate.get('type', 'xpath').lower()
            selector_value = candidate.get('value')
            
            # Convert string strategy sang Selenium By
            by_strategy = self.STRATEGY_MAP.get(strategy_str, By.XPATH)

            if self._is_element_present(driver, by_strategy, selector_value):
                logger.info(f"[SuggestionLayer] Candidate hợp lệ (Found in DOM): {selector_value}")
                
                # Chuẩn hóa output để các layer sau dễ dùng
                valid_candidates.append({
                    "locator": (by_strategy, selector_value),
                    "score": candidate.get('score', 1.0), # Suggestion thường có độ tin cậy cao
                    "source": "knowledge_base"
                })
            else:
                logger.debug(f"[SuggestionLayer] Candidate từ KB không tồn tại trong DOM: {selector_value}")

        if valid_candidates:
            logger.info(f"[SuggestionLayer] Tìm thấy {len(valid_candidates)} candidates hợp lệ.")
            return valid_candidates
            
        logger.info("[SuggestionLayer] Có gợi ý từ KB nhưng verify thất bại. Chuyển tiếp sang Layer 2.")
        return None

    def _is_element_present(self, driver: WebDriver, by: Any, value: str) -> bool:
        """Helper: Kiểm tra nhanh element có tồn tại không mà không throw exception"""
        try:
            # Dùng find_elements (số nhiều) trả về list rỗng nếu không thấy -> Không throw exception
            elements = driver.find_elements(by, value)
            return len(elements) > 0
        except Exception:
            return False

    def report_successful_heal(
        self,
        old_locator: Tuple[str, str],
        new_locator: Tuple[str, str],
        commit_info: Dict[str, Any],
        score: float = 1.0,
        page_url: Optional[str] = None,
    ) -> None:
        """
        Sau khi heal thành công (ở bất kỳ layer nào), gọi hàm này để update lại Knowledge Base.
        Dữ liệu này sẽ phục vụ cho SuggestionLayer ở lần chạy sau.
        """
        if self.last_fingerprint is None:
            logger.warning("[SuggestionLayer] Không có fingerprint (do lỗi bước init). Không thể update KB.")
            return

        logger.info(f"[SuggestionLayer] Learning: Cập nhật mapping {old_locator} -> {new_locator} vào KB.")
        
        try:
            self.cloud_kb_client.update_knowledge(
                fingerprint=self.last_fingerprint, # Key: Locator cũ (đặc điểm tĩnh)
                old_locator=old_locator,           # Thông tin raw locator cũ
                new_locator=new_locator,           # Value: Locator mới (đã verify)
                commit_info=commit_info,
                page_url=page_url,
                score=score
            )
        except Exception as e:
            logger.error(f"[SuggestionLayer] Lỗi khi cập nhật KB: {e}")