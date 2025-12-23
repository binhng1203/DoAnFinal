# self_healing_v1/layers/suggestion_layer.py
import json
from datetime import datetime

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
        logger.info(f"[SuggestionLayer] Initialized (Enabled: {self.enabled})")

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
    @property
    def enabled(self):
        """Kiểm tra trạng thái online của Client một cách an toàn"""
        return getattr(self.cloud_kb_client, 'enabled', False)

    def find_suggestion(self, fingerprint, locator_value):
        """
        [LAYER 1] Điểm tiếp nhận từ Manager.
        """
        # Sửa lỗi AttributeError: Kiểm tra thông qua property enabled
        if not self.enabled:
            return None
            
        # Gọi xuống Client để lấy dữ liệu
        return self.cloud_kb_client.find_suggestion(fingerprint, locator_value)
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

    def report_successful_heal(self, broken_locator, healed_locator, page_url, score, engine_name="lcs", repair_time_ms=0):
        logger.info(f"[SuggestionLayer] 🧠 BẮT ĐẦU lưu tri thức: {broken_locator[1]} -> {healed_locator[1]}")
        
        if not self.enabled:
            logger.warning("[SuggestionLayer] ⚠️ Bỏ qua vì SuggestionLayer đang Disabled.")
            return

        try:
            # Sử dụng chính xác cấu trúc mà Client mong đợi
            fp_dict = {
                "page_url": page_url,
                "locator_by": broken_locator[0],
                "locator_value": broken_locator[1]
            }
            
            # GỌI XUỐNG CLIENT
            self.cloud_kb_client.update_knowledge(
                old_locator=broken_locator,
                new_locator=healed_locator,
                fingerprint=fp_dict,
                page_url=page_url,
                engine=engine_name,
                score=score,
                duration_ms=repair_time_ms
            )
        except Exception as e:
            logger.error(f"[SuggestionLayer] ❌ Lỗi khi chuyển tiếp tri thức tới Client: {e}")