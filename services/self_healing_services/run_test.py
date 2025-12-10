# run_test.py
import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from self_healing_v1.manager import HealingManager
from self_healing_v1.wrapper import HealingWrapper
from test_cases.test_checkout_flow import run_checkout_happy_test
from test_cases.test_checkout_flow import run_checkout_healenium_native_sim_test
from test_cases.test_checkout_flow import run_checkout_python_fallback_sim_test

def build_db_config_from_env(prefix: str):
    return {
        # nếu chạy bên ngoài Docker → localhost
        # nếu chạy trong Docker → đổi localhost thành system_db
        "host": os.getenv(f"{prefix}HOST", "localhost"),
        "port": int(os.getenv(f"{prefix}PORT", "5432")),
        "dbname": os.getenv(f"{prefix}NAME", "final"),
        # User đọc/ghi knowledge base
        "user": os.getenv(f"{prefix}USER", "postgres"),
        "password": os.getenv(f"{prefix}PASSWORD", "postgres"),
    }

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s"
    )

    # -------------------------
    #  DB CONFIGS
    # -------------------------
    # Python fallback (knowledge base)
    db_config_kb = build_db_config_from_env("KB_DB_")
    # reporting / history → cũng nằm trong final.custom_analytics
    db_config_reporting = build_db_config_from_env("REPORT_DB_")

    # -------------------------
    #  MANAGER (Pipeline Python)
    # -------------------------
    manager = HealingManager(
        db_config_kb=db_config_kb,
        db_config_reporting=db_config_reporting,
        # healenium backend
        healenium_host="http://localhost:7878",
        visual_baseline_dir="visual_baseline",
    )

    # fallback python
    manager.enable_python_fallback = True
    # -------------------------
    #  WRAPPER (optional)
    # -------------------------
    # Vẫn khởi tạo nếu sau này bạn có test dùng wrapper.find_element()
    wrapper = HealingWrapper(manager)

    # -------------------------
    #  SELENIUM REMOTE (8085)
    # -------------------------
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")

    driver = webdriver.Remote(
        command_executor="http://localhost:8085/wd/hub",
        options=chrome_options,
    )

    try:
        # test_entrypoint sẽ nhận driver, healing_find_func, test_id, run_id, ...
        # từ manager.run_test_wrapper
        def test_entrypoint(**kwargs):
            # Không truyền wrapper vào đây nữa,
            # vì run_checkout_happy_test đang nhận driver + healing_find_func
            return run_checkout_healenium_native_sim_test(**kwargs)

        manager.run_test_wrapper(
            test_function=test_entrypoint,
            driver=driver,
            test_id="run_checkout_healenium_native_sim_test",
            wrapper=None,               # tham số này giờ không dùng nữa, nhưng giữ cho khỏi lỗi
            build_version="build-01",
            git_hash="sim-0001",
            app_version="1.0.0",
            author="Xuyn",
            fullscreen_page_name="checkout_country",  # tên logic, map tới baseline fullscreen
        )

    finally:
        driver.quit()
        manager.close()


if __name__ == "__main__":
    main()
