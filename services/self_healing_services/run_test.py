# run_test.py
import logging
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from self_healing_v1.manager import HealingManager
from self_healing_v1.wrapper import HealingWrapper
from test_cases.test_checkout_flow import run_checkout_happy_test


def build_db_config_from_env(prefix: str):
    return {
        # nếu chạy bên ngoài Docker → localhost
        # nếu chạy trong Docker → đổi localhost thành system_db
        "host": os.getenv(f"{prefix}HOST", "localhost"),

        "port": int(os.getenv(f"{prefix}PORT", "5432")),

        # 👉 GIỜ DÙNG CHUNG DB final (KHÔNG PHẢI healenium)
        "dbname": os.getenv(f"{prefix}NAME", "final"),

        # User đọc/ghi knowledge base
        "user": os.getenv(f"{prefix}USER", "healenium_user"),
        "password": os.getenv(f"{prefix}PASSWORD", "YDk2nmNs4s9aCP6K"),
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
    #  WRAPPER
    # -------------------------
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
        def test_entrypoint(**kwargs):
            return run_checkout_happy_test(
                wrapper=wrapper,
                **kwargs
            )

        manager.run_test_wrapper(
            test_function=test_entrypoint,
            driver=driver,
            test_id="run_checkout_happy_test",
            wrapper=None,
            build_version="build-01",
            git_hash="sim-0001",
            app_version="1.0.0",
            author="Xuyn",
        )

    finally:
        driver.quit()
        manager.close()


if __name__ == "__main__":
    main()
