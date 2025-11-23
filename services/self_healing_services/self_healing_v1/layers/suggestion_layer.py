# self_healing_v1/layers/suggestion_layer.py

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from selenium.webdriver.remote.webdriver import WebDriver


from ..utils.element_fingerprint import ElementFingerprint
from ..services.cloud_kb_client import CloudKnowledgeBaseClient

logger = logging.getLogger(__name__)


class SuggestionLayer:
    def __init__(self, cloud_kb_client: CloudKnowledgeBaseClient):
        self.cloud_kb_client = cloud_kb_client
        self.last_fingerprint: Optional[Dict[str, Any]] = None

    def get_suggestions(
        self,
        broken_locator: Tuple[str, str],
        driver: WebDriver,
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:

        print("[H01] Bắt đầu tạo fingerprint cho locator hỏng...")
        fingerprint_generator = ElementFingerprint(broken_locator, driver)
        self.last_fingerprint = fingerprint_generator.get()

        if not self.last_fingerprint:
            print("[H01] Không thể tạo fingerprint, bỏ qua SuggestionLayer.")
            return None

        page_url = None
        try:
            page_url = driver.current_url
        except Exception:
            pass

        print("[H02] Bắt đầu truy vấn healing_knowledge (public KB)...")
        suggestions = self.cloud_kb_client.get_suggestions(
            fingerprint=self.last_fingerprint,
            page_url=page_url
        )

        if isinstance(suggestions, list):
            if len(suggestions) == 0:
                return None
            if len(suggestions) == 1:
                return suggestions[0]
            return suggestions

        return suggestions

    def report_successful_heal(
        self,
        old_locator: Tuple[str, str],
        new_locator: Tuple[str, str],
        commit_info: Dict[str, Any],
        source: str = "python_fallback",
        score: float = 1.0,
        duration_ms: Optional[int] = None,
        page_url: Optional[str] = None,
    ) -> None:

        if self.last_fingerprint is None:
            print("[H03] Không có fingerprint để báo cáo.")
            return

        print("[H03] Báo cáo heal thành công lên healing_knowledge...")
        try:
            self.cloud_kb_client.update_knowledge(
                old_locator=old_locator,
                new_locator=new_locator,
                fingerprint=self.last_fingerprint,
                commit_info=commit_info,
                page_url=page_url,
                engine="PYTHON" if source != "native" else "NATIVE",
                score=score,
                duration_ms=duration_ms,
            )
        except Exception as e:
            print(f"[H03] Lỗi khi cập nhật KB: {e}")