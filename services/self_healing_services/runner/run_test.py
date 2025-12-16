# run_test.py
import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# =======================================================
# IMPORT CHUẨN (Giả định PYTHONPATH đã được set đúng)
# =======================================================
from self_healing_v1.manager import HealingManager
# Import từ root project vào folder runner
from runner.generic_executor import run_steps_test 
from runner.db_loader import load_test_definition_from_db
# =======================================================

def build_db_config_from_env(prefix: str):
    return {
        "host": os.getenv(f"{prefix}HOST", "localhost"),
        "port": int(os.getenv(f"{prefix}PORT", "5432")),
        "dbname": os.getenv(f"{prefix}NAME", "final"),
        "user": os.getenv(f"{prefix}USER", "postgres"),
        "password": os.getenv(f"{prefix}PASSWORD", "postgres"),
    }

def _create_manager():
    db_config_reporting = build_db_config_from_env("REPORT_DB_")
    manager = HealingManager(
        db_config_reporting=db_config_reporting,
        healenium_host="http://localhost:7878",
        visual_baseline_dir="visual_baseline",
    )
    return manager

def _create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    driver = webdriver.Remote(
        command_executor="http://localhost:8085",
        options=chrome_options,
    )
    return driver

def run_test_by_case_id(test_case_id: str):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    
    db_config_tests = build_db_config_from_env("TEST_DB_")
    
    try:
        test_definition = load_test_definition_from_db(
            test_case_id=test_case_id,
            db_config=db_config_tests,
        )
    except Exception as e:
        return {"status": "error", "message": f"DB Error: {e}"}

    if not test_definition:
        return {"status": "error", "message": f"Not found case {test_case_id}"}

    test_id = test_definition["test_id"]
    test_name = test_definition["name"]
    author = str(test_definition.get("assignee_user_id") or "unknown")

    logging.info(f"Running testcase: {test_name} ({test_id})")

    manager = None
    driver = None

    try:
        manager = _create_manager()
        driver = _create_driver()

        def test_entrypoint(**kwargs):
            return run_steps_test(
                driver=kwargs["driver"],
                healing_find_func=kwargs["healing_find_func"],
                test_definition=test_definition,
            )

        manager.run_test_wrapper(
            test_function=test_entrypoint,
            driver=driver,
            test_id=test_id,
            app_version=test_definition.get("app_version", "1.0.0"),
            author=author,
            fullscreen_page_name=test_definition.get("fullscreen_page_name", "default"),
        )
        return {"status": "success", "message": f"Run testcase '{test_name}' passed"}

    except Exception as e:
        logging.exception(f"Error running {test_name}")
        return {"status": "error", "message": str(e)}

    finally:
        if driver: 
            try: driver.quit()
            except: pass
        if manager: 
            try: manager.close()
            except: pass

if __name__ == "__main__":
    demo_case_id = "PUT-YOUR-UUID-HERE"
    print(run_test_by_case_id(demo_case_id))