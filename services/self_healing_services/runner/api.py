from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import logging
import os
import sys

# =========================================
# FIX IMPORT PATH
# =========================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))       
SERVICE_ROOT = os.path.dirname(CURRENT_DIR)                    
PROJECT_ROOT = os.path.dirname(SERVICE_ROOT)                   

for p in [PROJECT_ROOT, SERVICE_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

# =========================================
# IMPORT INTERNAL MODULES
# =========================================
from self_healing_v1.manager import HealingManager
from generic_executor import run_steps_test
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# =========================================
app = FastAPI()
logger = logging.getLogger(__name__)


# ======== DB CONFIG ============
DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "final",
    "user": "healenium_user",
    "password": "YDk2nmNs4s9aCP6K",
}

# ======== REQUEST MODEL ========
class RunRequest(BaseModel):
    test_case_id: str



# ======== API: RUN TEST ============
@app.post("/run_testcase")
def run_testcase(req: RunRequest):

    test_case_id = req.test_case_id

    # 1) Kết nối DB
    try:
        conn = psycopg2.connect(**DB)
        cur = conn.cursor()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB connect error: {e}")

    # 2) Lấy test case
    cur.execute("""
        SELECT case_id, name, priority, type, description, suite_id,
               fullscreen_page_name, app_version, build_version, git_hash
        FROM management.test_cases
        WHERE case_id = %s
    """, (test_case_id,))
    
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Test case not found")

    case = {
        "case_id": row[0],
        "name": row[1],
        "priority": row[2],
        "type": row[3],
        "description": row[4],
        "suite_id": row[5],
        "fullscreen_page_name": row[6],
        "app_version": row[7],
        "build_version": row[8],
        "git_hash": row[9],
    }

    # 3) Lấy test steps
    cur.execute("""
        SELECT step_order, action, locator_type, locator_value, value, url, expected
        FROM management.test_steps
        WHERE test_case_id = %s
        ORDER BY step_order ASC
    """, (test_case_id,))

    steps = []
    for s in cur:
        steps.append({
            "order": s[0],
            "action": s[1],
            "locator_type": s[2],
            "locator_value": s[3],
            "value": s[4],
            "url": s[5],
            "expected": s[6],
        })

    if len(steps) == 0:
        raise HTTPException(status_code=400, detail="No steps found for testcase")

    # Build test_definition
    test_definition = {
        "test_id": case["case_id"],
        "name": case["name"],
        "steps": steps
    }

    # 4) Init Healenium manager
    manager = HealingManager(
        db_config_kb=DB,
        db_config_reporting=DB,
        healenium_host="http://localhost:7878",
        visual_baseline_dir="visual_baseline"
    )
    manager.enable_python_fallback = True

    # 5) Init Selenium Remote
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")

    driver = webdriver.Remote(
        command_executor="http://localhost:8085/wd/hub",
        options=chrome_options,
    )

    # 6) Gọi test runner
    try:

        def entrypoint(**kwargs):
            return run_steps_test(
                driver=kwargs["driver"],
                healing_find_func=kwargs["healing_find_func"],
                test_definition=test_definition
            )

        manager.run_test_wrapper(
            test_function=entrypoint,
            driver=driver,
            test_id=str(case["case_id"]),
            wrapper=None,
            build_version=case["build_version"],
            git_hash=case["git_hash"],
            app_version=case["app_version"],
            author="system-api",
            fullscreen_page_name=case["fullscreen_page_name"]
        )

        status = "passed"

    except Exception as e:
        status = "failed"
        logger.exception("Test failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Test execution failed: {e}")

    finally:
        driver.quit()
        manager.close()
        cur.close()
        conn.close()

    # 7) Trả kết quả JSON cho Postman
    return {
        "test_case_id": test_case_id,
        "test_case_name": case["name"],
        "status": status,
        "steps": len(steps)
    }
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)

