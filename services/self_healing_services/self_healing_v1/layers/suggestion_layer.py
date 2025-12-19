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

    def report_successful_heal(self, *args, **kwargs):
        pass
    def report_successful_heal(
        self, 
        broken_locator: Tuple[str, str], 
        healed_locator: Tuple[str, str], 
        page_url: str,
        score: float,
        engine_name: str = "lcs", 
        repair_time_ms: int = 0
    ):
        """
        Ghi nhận kết quả healing khớp 100% với bảng public.healing_knowledge.
        """
        if not self.cloud_kb_client or not self.cloud_kb_client.enabled:
            return

        try:
            old_by, old_val = broken_locator
            new_by, new_val = healed_locator

            # 1. Tạo Fingerprint (Sử dụng cấu trúc đồng bộ với Manager và Client)
            fingerprint_dict = {
                "page_url": page_url,
                "locator_by": old_by,
                "locator_value": old_val
            }
            
            # Tạo Hash phục vụ cột fingerprint_hash (Variant A)
            fp_json = json.dumps(fingerprint_dict, sort_keys=True)
            fp_hash = hashlib.sha256(fp_json.encode()).hexdigest()

            # 2. Chuẩn bị payload khớp TÊN CỘT trong DB của bạn
            # Chú ý: Sử dụng 'last_updated' thay vì 'updated_at'
            payload = {
                "fingerprint_hash": fp_hash,
                "fingerprint_json": fingerprint_dict, # Để client bọc Json() sau
                "old_locator_by": old_by,
                "old_locator_value": old_val,
                "new_locator_by": new_by,
                "new_locator_value": new_val,
                "last_score": score,
                "last_engine": engine_name,
                "avg_repair_ms": repair_time_ms,
                "source_type": "self_healing_v1",
                "last_updated": datetime.now().isoformat(),
                "project_id": None # Sẽ được resolve bên trong Client
            }

            logger.info(f"[SuggestionLayer] 🧠 Đang lưu tri thức mới: {old_val} -> {new_val}")
            
            # 3. Gửi sang Client để thực hiện INSERT/UPDATE
            if hasattr(self.cloud_kb_client, "save_healing_result"):
                self.cloud_kb_client.save_healing_result(payload)
                
        except Exception as e:
            logger.error(f"[SuggestionLayer] Lỗi chuẩn bị dữ liệu KB: {e}")