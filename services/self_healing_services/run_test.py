import sys
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Import từ project
from self_healing_v1.manager import HealingManager
from test_cases.add_to_card import run_minimal_shop_happy_test

def build_db_config_from_env(prefix: str):
    return {
        "host": os.getenv(f"{prefix}HOST", "localhost"),
        "port": int(os.getenv(f"{prefix}PORT", "5432")),
        "dbname": os.getenv(f"{prefix}NAME", "final"),
        "user": os.getenv(f"{prefix}USER", "postgres"),
        "password": os.getenv(f"{prefix}PASSWORD", "postgres"),
    }

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    
    # 1. Config DB (Vẫn giữ để Manager ghi log report riêng nếu muốn)
    db_config_reporting = build_db_config_from_env("REPORT_DB_")

    manager = HealingManager(
        db_config_reporting=db_config_reporting,
        visual_baseline_dir="visual_baseline",
    )

    # 2. Setup Driver kết nối qua PROXY
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    # Có thể thêm capability nếu cần cấu hình Healenium
    # chrome_options.set_capability("healenium:options", {"recovery-tries": 1})

    print(">>> [INIT] Connecting to Healenium Proxy at http://localhost:8085 ...")
    
    # [THAY ĐỔI QUAN TRỌNG NHẤT Ở ĐÂY]
    driver = webdriver.Remote(
        command_executor="http://localhost:8085",  # Địa chỉ Healenium Proxy
        options=chrome_options
    )

    try:
        def test_entrypoint(driver, manager):
            return run_minimal_shop_happy_test(
                driver=driver,
                healing_find_func=manager.find_element,
                test_id=manager._current_test_id,
                run_id=manager._current_run_id
            )

        manager.run_test_wrapper(
            test_function=test_entrypoint,
            driver=driver,
            test_id="run_minimal_shop_happy_test_proxy", # Đổi tên chút để phân biệt
            app_version="1.0.0",
        )
    finally:
        driver.quit()
        manager.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ [EXECUTION FAILED]: {e}")
        sys.exit(1)