import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC # Sửa lỗi EC is not defined

_BY_MAPPING = {
    "id": By.ID, 
    "xpath": By.XPATH, 
    "css": By.CSS_SELECTOR, 
    "name": By.NAME, 
    "class": By.CLASS_NAME
}

def run_steps_directly(steps_data, test_name, timeout=15):
    """
    F05 - Thực thi targeted smoke test và trả về chi tiết lỗi cụ thể.
    """
    results = {
        "status": "PASS",
        "passed": 0, "failed": 0, "total": 0,
        "details": [],
        "runner": {"test_name": test_name, "type": "Selenium_Standalone_Remote"}
    }
    if not steps_data: return results

    # Theo dõi step để báo cáo khi fail
    current_step_info = {"order": "N/A", "action": "init"}
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = None
    try:
        remote_url = "http://selenium-chrome:4444/wd/hub"
        driver = webdriver.Remote(command_executor=remote_url, options=options)
        
        def wait_and_find(l_type, l_val):
            by_strat = _BY_MAPPING.get(str(l_type).lower().strip(), By.XPATH)
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by_strat, l_val))
            )

        for step in steps_data:
            current_step_info["order"] = step.get("order", "Unknown")
            current_step_info["action"] = (step.get("action") or "").lower().strip()
            
            l_type = (step.get("locator_type") or "xpath")
            l_val = step.get("locator_value")
            val = step.get("value")

            if current_step_info["action"] == "open_url":
                driver.get(step.get("url") or val)
                WebDriverWait(driver, timeout).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            elif current_step_info["action"] == "click":
                wait_and_find(l_type, l_val).click()
            elif current_step_info["action"] in ["type", "input"]:
                el = wait_and_find(l_type, l_val)
                el.clear()
                el.send_keys(str(val if val is not None else ""))
            
            time.sleep(1)

        results["passed"] = 1

    except Exception as e:
        results["status"] = "FAIL"
        results["failed"] = 1
        
        # Bóc tách lỗi sạch sẽ, dứt điểm "Message: Message:"
        raw_error = str(e).split('Stacktrace:')[0].replace("Message: ", "").strip()
        
        results["details"].append({
            "error": raw_error,
            "failed_at_step": current_step_info["order"],
            "failed_action": current_step_info["action"]
        })
        print(f"FAIL at step {current_step_info['order']}: {raw_error}")

    finally:
        results["total"] = results["passed"] + results["failed"]
        if driver: driver.quit()

    return results