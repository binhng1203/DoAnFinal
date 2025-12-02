# run_test.py
import logging
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from self_healing_v1.manager import HealingManager
from generic_executor import run_steps_test
from db_loader import load_test_definition_from_db


def build_db_config_from_env(prefix: str):
    return {
        "host": os.getenv(f"{prefix}HOST", "localhost"),
        "port": int(os.getenv(f"{prefix}PORT", "5432")),
        "dbname": os.getenv(f"{prefix}NAME", "final"),
        "user": os.getenv(f"{prefix}USER", "healenium_user"),
        "password": os.getenv(f"{prefix}PASSWORD", "YDk2nmNs4s9aCP6K"),
    }


def _create_manager():
    db_config_kb = build_db_config_from_env("KB_DB_")
    db_config_reporting = build_db_config_from_env("REPORT_DB_")

    manager = HealingManager(
        db_config_kb=db_config_kb,
        db_config_reporting=db_config_reporting,
        healenium_host="http://localhost:7878",
        visual_baseline_dir="visual_baseline",
    )
    manager.enable_python_fallback = True
    return manager


def _create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")

    driver = webdriver.Remote(
        command_executor="http://localhost:8085/wd/hub",
        options=chrome_options,
    )
    return driver


def run_test_by_case_id(test_case_id: str):
    """
    Nhận test_case_id (UUID), load testcase + steps từ DB, rồi chạy với Healenium.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s"
    )

    # DB dùng cho test_cases / test_steps
    db_config_tests = build_db_config_from_env("TEST_DB_")

    # 1. Load test_definition
    test_definition = load_test_definition_from_db(
        test_case_id=test_case_id,
        db_config=db_config_tests,
    )

    if not test_definition:
        return {
            "status": "error",
            "message": f"Không tìm thấy test_case_id = {test_case_id}"
        }

    test_id = test_definition["test_id"]       # uuid
    test_name = test_definition["name"]        # tên testcase
    author = (
        str(test_definition["assignee_user_id"])
        if test_definition.get("assignee_user_id") else "unknown"
    )

    logging.info("Running testcase: %s (%s)", test_name, test_id)

    manager = _create_manager()
    driver = _create_driver()

    try:
        def test_entrypoint(**kwargs):
            return run_steps_test(
                driver=kwargs["driver"],
                healing_find_func=kwargs["healing_find_func"],
                test_definition=test_definition,
            )

        manager.run_test_wrapper(
            test_function=test_entrypoint,
            driver=driver,
            # vẫn dùng uuid làm test_id kỹ thuật, tên test dùng cho log
            test_id=test_id,
            wrapper=None,
            build_version=test_definition.get("build_version") or "dev",
            git_hash=test_definition.get("git_hash") or "unknown",
            app_version=test_definition.get("app_version") or "1.0.0",
            author=author,  # <-- chính là assignee_user_id
            fullscreen_page_name=test_definition.get("fullscreen_page_name", "default"),
            # nếu run_test_wrapper hỗ trợ thêm field khác, bạn có thể
            # truyền test_name qua kwargs (ví dụ test_name=test_name)
        )

        return {
            "status": "success",
            "message": f"Run testcase '{test_name}' thành công"
        }

    except Exception as e:
        logging.exception("Error while running testcase %s (%s)", test_name, test_id)
        return {
            "status": "error",
            "message": str(e)
        }

    finally:
        driver.quit()
        manager.close()


if __name__ == "__main__":
    demo_case_id = "PUT-YOUR-UUID-HERE"
    print(run_test_by_case_id(demo_case_id))
