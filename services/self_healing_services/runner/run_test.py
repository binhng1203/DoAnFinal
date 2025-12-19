# run_test.py
import os
import sys
import logging
import traceback
from typing import Dict, Any, List

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# =====================================================
# 1. FIX IMPORT PATH (CHO DOCKER / UVICORN)
# =====================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

if project_root not in sys.path:
    sys.path.insert(0, project_root)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# =====================================================
# 2. IMPORT CORE MODULES
# =====================================================
from self_healing_v1.manager import HealingManager

try:
    from runner.generic_executor import run_steps_test
except ImportError:
    from generic_executor import run_steps_test

# =====================================================
# 3. FASTAPI APP
# =====================================================
app = FastAPI()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# =====================================================
# 4. ENV CONFIG
# =====================================================
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "final")
DB_USER = os.environ.get("DB_USER", "app_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "app_password")

HEALENIUM_HOST = os.environ.get("HEALENIUM_HOST", "http://localhost:7878")
SELENIUM_HOST = os.environ.get("SELENIUM_HOST", "http://localhost:8085/wd/hub")

DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
}

# =====================================================
# 5. REQUEST MODEL
# =====================================================
class RunRequest(BaseModel):
    test_case_id: int

# =====================================================
# 6. API ENDPOINT
# =====================================================
@app.post("/run_testcase")
def run_testcase(req: RunRequest):

    test_case_id = req.test_case_id

    conn = None
    cur = None
    driver = None
    manager = None

    status = "FAILED"
    case: Dict[str, Any] = {}
    steps: List[Dict[str, Any]] = []

    try:
        # =================================================
        # 1️⃣ CONNECT DB
        # =================================================
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # =================================================
        # 2️⃣ LOAD TEST CASE
        # =================================================
        cur.execute(
            """
            SELECT case_id, name, priority, case_type, description,
                   suite_id, fullscreen_page_name, app_version
            FROM management.test_cases
            WHERE case_id = %s
            """,
            (test_case_id,),
        )
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
            "app_version": row[7] or "1.0.0",
        }

        # =================================================
        # 3️⃣ LOAD TEST STEPS
        # =================================================
        cur.execute(
            """
            SELECT step_order, action, locator_type, locator_value,
                   value, url, expected
            FROM management.test_steps
            WHERE case_id = %s
            ORDER BY step_order ASC
            """,
            (test_case_id,),
        )

        for s in cur.fetchall():
            steps.append(
                {
                    "order": s[0],
                    "action": s[1],
                    "locator_type": s[2],
                    "locator_value": s[3],
                    "value": s[4],
                    "url": s[5],
                    "expected": s[6],
                }
            )

        if not steps:
            raise HTTPException(status_code=400, detail="No steps found")

        # =================================================
        # 4️⃣ BUILD TEST DEFINITION (ENGINE INPUT)
        # =================================================
        test_definition = {
            "test_id": str(case["case_id"]),
            "name": case["name"],
            "steps": steps,
            "meta": {
                "priority": case["priority"],
                "suite_id": case["suite_id"],
                "case_type": case["type"],
            },
        }

        # =================================================
        # 5️⃣ INIT HEALING MANAGER
        # =================================================
        manager = HealingManager(
            db_config_reporting=DB_CONFIG,
            db_config_kb=DB_CONFIG,
            healenium_host=HEALENIUM_HOST,
            visual_baseline_dir="visual_baseline",
        )

        # =================================================
        # 6️⃣ INIT SELENIUM
        # =================================================
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Remote(
            command_executor=SELENIUM_HOST,
            options=chrome_options,
        )

        # =================================================
        # 7️⃣ ENTRYPOINT – CHUẨN CONTRACT MANAGER
        # =================================================
        def entrypoint(
            driver,
            healing_find_func,
            test_id,
            run_id,
            **kwargs,
        ):
            """
            ⚠️ CONTRACT BẮT BUỘC
            """
            return run_steps_test(
                driver=driver,
                healing_find_func=healing_find_func,
                test_definition=test_definition,
                test_id=test_id,
                run_id=run_id,
            )

        # =================================================
        # 8️⃣ RUN TEST
        # =================================================
        manager.run_test_wrapper(
            test_function=entrypoint,
            driver=driver,
            test_id=str(case["case_id"]),
            app_version=case["app_version"],
            author="system-api",
            fullscreen_page_name=case["fullscreen_page_name"],
        )

        status = "PASSED"

    except HTTPException:
        raise

    except Exception as e:
        logger.error("Test execution failed", exc_info=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        if manager:
            try:
                manager.close()
            except Exception:
                pass
        if cur:
            cur.close()
        if conn:
            conn.close()

    # =====================================================
    # 9️⃣ API RESPONSE
    # =====================================================
    return {
        "test_case_id": test_case_id,
        "test_case_name": case.get("name"),
        "status": status,
        "total_steps": len(steps),
    }


# =====================================================
# 10. LOCAL RUN
# =====================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
