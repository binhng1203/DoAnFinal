import os
import time
import logging
from typing import Any, Dict, List, Callable
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from self_healing_v1.manager import HealingManager

logger = logging.getLogger(__name__)

# Mapping locator string sang Selenium By
_BY_MAPPING = {
    "id": By.ID, "xpath": By.XPATH, "css": By.CSS_SELECTOR,
    "class_name": By.CLASS_NAME, "name": By.NAME
}

def run_steps_test(driver, healing_find_func, test_definition, **kwargs):
    """
    Hàm thực thi từng bước (Action Engine).
    Sử dụng healing_find_func để kích hoạt Self-healing của Manager.
    """
    steps = sorted(test_definition.get("steps", []), key=lambda s: s.get("order", 0))
    timeout = kwargs.get("timeout", 15)

    for step in steps:
        action = step.get("action", "").lower().strip()
        l_type = step.get("locator_type")
        l_val = step.get("locator_value")
        val = step.get("value")
        
        # Tạo context để Manager biết đang ở step nào (phục vụ Decision/Validation Layer)
        test_context = {
            "test_id": test_definition.get("test_id"),
            "step_order": step.get("order"),
            "step_action": action
        }

        try:
            if action == "open_url":
                driver.get(step.get("url"))
                # Đợi trang load xong hoàn toàn trước khi tiếp tục
                WebDriverWait(driver, timeout).until(lambda d: d.execute_script('return document.readyState') == 'complete')

            elif action == "click":
                by = _BY_MAPPING.get(l_type, By.ID)
                el = healing_find_func(by=by, value=l_val, element_name=f"Step_{step.get('order')}", test_context=test_context)
                el.click()

            elif action == "type":
                by = _BY_MAPPING.get(l_type, By.ID)
                el = healing_find_func(by=by, value=l_val, element_name=f"Step_{step.get('order')}", test_context=test_context)
                el.clear()
                el.send_keys(str(val))

            elif action == "wait_seconds":
                time.sleep(float(val or 1))

            elif action == "assert_text":
                by = _BY_MAPPING.get(l_type, By.ID)
                el = healing_find_func(by=by, value=l_val, element_name=f"Step_{step.get('order')}", test_context=test_context)
                assert (step.get("expected") or "").strip() in el.text
        
        except Exception as e:
            logger.error(f"Lỗi tại step {step.get('order')}: {e}")
            raise e

def execute_test_logic(case, steps, db_config):
    """
    Wrapper khởi tạo Manager và Driver qua Healenium Proxy.
    Đảm bảo đóng driver sạch sẽ sau khi xong.
    """
    manager = None
    driver = None
    try:
        # Khởi tạo Manager (Ghi log vào bảng reporting và KB)
        manager = HealingManager(
            db_config_kb=db_config,
            db_config_reporting=db_config,
            healenium_host=os.environ.get("HEALENIUM_HOST", "http://healenium:7878"),
            visual_baseline_dir="/app/visual_baseline"
        )

        chrome_options = Options()
        chrome_options.add_argument("--headless") # Chạy trong Docker không màn hình
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Kết nối qua Healenium Proxy (Port 8085)
        driver = webdriver.Remote(
            command_executor=os.environ.get("SELENIUM_HOST", "http://hlm-proxy:8085/wd/hub"),
            options=chrome_options
        )

        # Chạy test qua Wrapper của Manager để kích hoạt Self-healing và lưu kết quả
        manager.run_test_wrapper(
            test_function=run_steps_test,
            driver=driver,
            test_id=str(case["case_id"]),
            app_version=case["app_version"],
            fullscreen_page_name=case["fullscreen_page_name"],
            test_definition={"test_id": str(case["case_id"]), "name": case["name"], "steps": steps}
        )
        return {"status": "passed"}

    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        if driver: driver.quit()
        if manager: manager.close()