# self_healing/utils/element_fingerprint.py

from typing import Dict, Any, Tuple
from selenium.webdriver.remote.webdriver import WebDriver


class ElementFingerprint:
    """
    (H01) Lớp tạo "vân tay" cho một locator bị lỗi.

    Fingerprint hiện tại gồm:
        - locator_by
        - locator_value
        - page_url

    Đủ để:
        - SuggestionLayer dùng query lên CloudKnowledgeBaseClient.
        - Bạn có thể mở rộng thêm sau (parent_attributes, context DOM, v.v.).
    """

    def __init__(self, broken_locator: Tuple[str, str], driver: WebDriver):
        self.broken_locator = broken_locator
        self.driver = driver

    def get(self) -> Dict[str, Any]:
        locator_by, locator_value = self.broken_locator
        current_url = self.driver.current_url

        # Nếu muốn bỏ query param động:
        # clean_url = current_url.split("?", 1)[0]
        clean_url = current_url

        fingerprint = {
            "locator_by": locator_by,
            "locator_value": locator_value,
            "page_url": clean_url,
        }

        print(f"[Fingerprint] Đã tạo vân tay: {fingerprint}")
        return fingerprint
