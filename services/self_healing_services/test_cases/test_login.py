# test_cases/test_login.py
import logging
from selenium.webdriver.common.by import By
from typing import Callable, Any

logger = logging.getLogger(__name__)

def run_login_test(driver: Any, healing_find_func: Callable, test_id: str, **kwargs): 
    """
    Kịch bản test này được "wrap" bởi HealingManager.
    Nó KHÔNG tự bắt lỗi.
    healing_find_func chính là 'wrapper.find_element'.
    """
    logger.info(f"--- Bắt đầu kịch bản test: {test_id} ---")
    
    test_context = {
        "test_id": test_id,
        "test_case_priority": "high",
        "commit_info": {
            "hash": "docker_run_index",
            "author": "Test User",
            "message": "Testing index.html"
        }
    }

    # === PHẦN 1: Truy cập trang Test ===
    app_url = "http://static-app/index.html" 
    driver.get(app_url)
    test_context["page_url"] = app_url 
    logger.info(f"Đã mở trang login từ Nginx container: {app_url}")

    # === PHẦN 2: Kiểm tra Locator ĐÚNG ===
    # <<< SỬA LỖI: Đã xóa 'driver=driver' >>>
    username = healing_find_func(
        by=By.ID,
        value="username",
        element_name="LoginPage_Input_Username",
        test_context=test_context
    )
    username.send_keys("test_user")
    logger.info("Tìm thấy và nhập 'username' thành công.")

    # === PHẦN 3: Kiểm tra Locator SAI (để kích hoạt Self-Healing) ===
    # <<< SỬA LỖI: Đã xóa 'driver=driver' >>>
    login_btn = healing_find_func(
        by=By.ID,
        value="submit-login-button_OLD", # LOCATOR HỎNG
        element_name="LoginPage_Button_LogIn",
        test_context=test_context
    )
    
    login_btn.click()
    logger.info("Tìm thấy (phục hồi) và click 'login_btn' thành công.")
    
    logger.info(f"--- Kịch bản test: {test_id} THÀNH CÔNG ---")