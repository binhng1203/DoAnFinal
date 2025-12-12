import logging
from typing import Any, Dict
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException

logger = logging.getLogger(__name__)

class SelfHealingDriver:
    """
    Wrapper bao bọc Selenium WebDriver để tự động kích hoạt Self-healing.
    """

    def __init__(self, driver: WebDriver, manager_instance):
        self.driver = driver
        self.manager = manager_instance
        self.current_test_context: Dict[str, Any] = {}

    def set_test_context(self, **kwargs):
        """Cập nhật context cho test case hiện tại"""
        self.current_test_context.update(kwargs)

    # --- SỬA LỖI Ở ĐÂY: Thêm **kwargs ---
    def find_element(self, by: str, value: str, **kwargs) -> WebElement:
        """
        Override hàm find_element.
        Chấp nhận thêm **kwargs (ví dụ: element_name) để tương thích với test script.
        """
        # 1. Trích xuất element_name nếu có (để dùng cho healing context đẹp hơn)
        custom_element_name = kwargs.get("element_name")
        
        try:
            # Lưu ý: Hàm gốc driver.find_element KHÔNG nhận kwargs, chỉ nhận by và value
            return self.driver.find_element(by, value)
        
        except NoSuchElementException:
            logger.warning(f"[Wrapper] ⚠️ Không tìm thấy element '{value}'. Kích hoạt Self-Healing...")
            
            # Chuẩn bị context cho healing
            healing_context = self.current_test_context.copy()
            
            # Nếu test script có truyền tên element, hãy dùng nó để log cho đẹp
            if custom_element_name:
                healing_context["element_name"] = custom_element_name

            # Gọi Healing Manager
            healed_element = self.manager.heal(
                driver=self.driver,
                by=by,
                value=value,
                test_context=healing_context
            )
            
            if healed_element:
                return healed_element
            
            # Nếu healing thất bại
            raise NoSuchElementException(f"Cannot find element '{value}' (Healing Failed)")

    # =========================================================================
    # CÁC HÀM PROXY 
    # =========================================================================
    
    @property
    def current_url(self):
        return self.driver.current_url

    @property
    def title(self):
        return self.driver.title
    
    @property
    def page_source(self):
        return self.driver.page_source

    def quit(self):
        self.driver.quit()

    def close(self):
        self.driver.close()

    def find_elements(self, by, value):
        return self.driver.find_elements(by, value)

    def __getattr__(self, name):
        """Chuyển tiếp các lệnh không có trong Wrapper sang Driver gốc"""
        return getattr(self.driver, name)