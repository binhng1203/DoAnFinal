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
    
    db_config_reporting = build_db_config_from_env("REPORT_DB_")

    # Init Manager
    manager = HealingManager(
        db_config_reporting=db_config_reporting,
        visual_baseline_dir="visual_baseline",
        healenium_host="http://localhost:7878"
    )

    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")

    print(">>> [INIT] Connecting to Healenium Proxy at http://localhost:8085 ...")
    
    driver = webdriver.Remote(
        command_executor="http://localhost:8085",
        options=chrome_options
    )

    try:
        def test_entrypoint(driver, healing_find_func, test_id, run_id, **kwargs):
            print(f"   -> [TestRunner] Bắt đầu test '{test_id}' với run_id={run_id}")
            return run_minimal_shop_happy_test(
                driver=driver,
                healing_find_func=healing_find_func,
                test_id=test_id,
                run_id=run_id,
                **kwargs
            )

        # --- [KÍCH HOẠT FULLSCREEN VALIDATION TẠI ĐÂY] ---
        manager.run_test_wrapper(
            test_function=test_entrypoint,
            driver=driver,
            test_id="run_minimal_shop_happy_test_proxy",
            app_version="1.0.0",
            
            # [THÊM DÒNG NÀY]: Đặt tên cho trang để Manager biết cần chụp ảnh validate cuối cùng
            fullscreen_page_name="Product_Detail_Page" 
        )

    except Exception as e:
        logging.error(f"Test Execution Failed: {e}")
        # Không raise e ở đây để code chạy xuống finally đóng driver sạch sẽ
        
    finally:
        print(">>> [TEARDOWN] Closing driver & manager...")
        try: driver.quit()
        except: pass
        manager.close()

if __name__ == "__main__":
    main()