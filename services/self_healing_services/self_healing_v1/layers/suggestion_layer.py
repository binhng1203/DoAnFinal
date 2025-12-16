# self_healing_v1/layers/suggestion_layer.py

import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Union
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

# Giữ nguyên import
from ..utils.element_fingerprint import ElementFingerprint
from ..services.cloud_kb_client import CloudKnowledgeBaseClient

logger = logging.getLogger(__name__)

# [CLASS WRAPPER] Để HealingManager truy cập kết quả bằng .attribute
class SuggestionResult:
    def __init__(self, data: Dict[str, Any]):
        self.new_locator_by = data.get("new_locator_by") or data.get("type")
        self.new_locator_value = data.get("new_locator_value") or data.get("value")
        self.success_rate = float(data.get("success_rate", 0.0) or data.get("score", 0.0))

class SuggestionLayer:
    """
    Layer 1: Suggestion
    Nhiệm vụ: Tra cứu nhanh từ Knowledge Base.
    """

    STRATEGY_MAP = {
        "id": By.ID, "xpath": By.XPATH, "link text": By.LINK_TEXT,
        "partial link text": By.PARTIAL_LINK_TEXT, "name": By.NAME,
        "tag name": By.TAG_NAME, "class name": By.CLASS_NAME,
        "css selector": By.CSS_SELECTOR, "css": By.CSS_SELECTOR
    }

    def __init__(self, cloud_kb_client: CloudKnowledgeBaseClient):
        self.cloud_kb_client = cloud_kb_client
        self.last_fingerprint: Optional[Dict[str, Any]] = None

    # ==========================================================================
    # [QUAN TRỌNG] Hàm này đã được sửa để nhận đủ 4 tham số từ Manager
    # và trả về cấu trúc khớp với DB (Fix lỗi KB Missed)
    # ==========================================================================
    def generate_fingerprint(
        self, 
        page_source: str, 
        locator_by: str, 
        locator_value: str, 
        page_url: str
    ) -> Dict[str, Any]:
        """
        Tạo fingerprint. 
        Lưu ý: Để tìm thấy dữ liệu trong DB (do Persistence lưu), 
        fingerprint phải chứa page_url và locator gốc.
        """
        try:
            logger.info(f"[SuggestionLayer] Đang tạo fingerprint cho: {locator_value}")
            
            # Cấu trúc này KHỚP với cấu trúc PersistenceService lưu xuống DB
            self.last_fingerprint = {
                "page_url": page_url,
                "locator_by": locator_by,
                "locator_value": locator_value
            }
            return self.last_fingerprint

        except Exception as e:
            logger.error(f"[SuggestionLayer] Lỗi tạo fingerprint: {e}")
            return {}

    # ==========================================================================
    # Hàm find_suggestion (Được HealingManager gọi)
    # ==========================================================================
    def find_suggestion(self, fingerprint: Dict[str, Any], locator_value: str) -> Optional[SuggestionResult]:
        """
        Tìm kiếm giải pháp trong KB.
        """
        if not self.cloud_kb_client:
            return None

        try:
            # 1. Thử query DB
            raw_data = None
            
            # Ưu tiên query chính xác theo JSON
            if hasattr(self.cloud_kb_client, "query_suggestion"):
                raw_data = self.cloud_kb_client.query_suggestion(fingerprint, locator_value)
                if raw_data:
                    return SuggestionResult(raw_data)
            
            # Fallback sang hàm cũ
            elif hasattr(self.cloud_kb_client, "get_suggestions"):
                suggestions = self.cloud_kb_client.get_suggestions(
                    fingerprint=fingerprint,
                    page_url=fingerprint.get("page_url", "unknown")
                )
                if suggestions:
                    best = suggestions[0] if isinstance(suggestions, list) else suggestions
                    # Map dữ liệu cũ sang cấu trúc mới
                    raw_data = {
                        "new_locator_by": best.get('type', 'xpath'),
                        "new_locator_value": best.get('value'),
                        "success_rate": best.get('score', 0.0)
                    }
                    return SuggestionResult(raw_data)

            return None

        except Exception as e:
            logger.error(f"[SuggestionLayer] Lỗi tìm suggestion: {e}")
            return None

    # ==========================================================================
    # Các hàm Legacy (Giữ lại để tương thích code cũ)
    # ==========================================================================
    def get_suggestions(self, broken_locator: Tuple[str, str], driver: WebDriver) -> Optional[List[Dict[str, Any]]]:
        """Legacy method"""
        # Logic cũ dùng ElementFingerprint (Hash), giữ nguyên để không ảnh hưởng code cũ
        # Nhưng Manager v1 sẽ không gọi hàm này nữa.
        try:
            fingerprint_generator = ElementFingerprint(broken_locator)
            self.last_fingerprint = fingerprint_generator.get()
            if not self.last_fingerprint: return None
            
            suggestions = self.cloud_kb_client.get_suggestions(
                fingerprint=self.last_fingerprint,
                page_url=driver.current_url
            )
            
            if not suggestions: return None
            
            candidates = suggestions if isinstance(suggestions, list) else [suggestions]
            valid = []
            for c in candidates:
                by = self.STRATEGY_MAP.get(c.get('type', 'xpath').lower(), By.XPATH)
                val = c.get('value')
                if self._is_element_present(driver, by, val):
                    valid.append({"locator": (by, val), "score": c.get('score', 1.0), "source": "knowledge_base"})
            return valid if valid else None
        except: return None

    def _is_element_present(self, driver: WebDriver, by: Any, value: str) -> bool:
        try: return len(driver.find_elements(by, value)) > 0
        except: return False

    def report_successful_heal(self, *args, **kwargs):
        pass