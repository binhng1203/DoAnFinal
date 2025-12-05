from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import logging
import os
import sys
import traceback

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
try:
    from self_healing_v1.manager import HealingManager
    from generic_executor import run_steps_test
except ImportError:
    pass # Bỏ qua lỗi import lúc dev, docker sẽ chạy ok

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# =========================================
app = FastAPI()
logger = logging.getLogger(__name__)

# ======== CONFIG TỪ DOCKER ENV (QUAN TRỌNG) ============
# Mặc định fallback là localhost để bạn chạy test tay vẫn được, 
# nhưng Docker sẽ ghi đè bằng biến môi trường
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = "final"
DB_USER = os.environ.get("DB_USER", "app_user")         
DB_PASSWORD = os.environ.get("DB_PASSWORD", "app_password")

HEALENIUM_HOST = os.environ.get("HEALENIUM_HOST", "http://localhost:7878")
SELENIUM_HOST = os.environ.get("SELENIUM_HOST", "http://localhost:8085/wd/hub")

DB_CONFIG = {
    "host": DB_HOST,
    "port": 5432,
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
}

# ======== REQUEST MODEL ========
class RunRequest(BaseModel):
    test_case_id: int 

# ======== API: RUN TEST ============
@app.post("/run_testcase")
def run_testcase(req: RunRequest):

    test_case_id = req.test_case_id
    
    conn = None
    cur = None
    driver = None
    manager = None
    
    try:
        # 1) Kết nối DB
        print(f"Connecting DB: {DB_HOST} as {DB_USER}...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
    
        # 2) Lấy test case
        # SỬA: Cột 'type' -> 'case_type' (theo db mới)
        cur.execute("""
            SELECT case_id, name, priority, case_type, description, suite_id,
                   fullscreen_page_name, app_version
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
            "build_version": "1.0",
            "git_hash": "HEAD"
        }
    
        # 3) Lấy test steps
        cur.execute("""
            SELECT step_order, action, locator_type, locator_value, value, url, expected
            FROM management.test_steps
            WHERE case_id = %s
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
            "test_id": str(case["case_id"]),
            "name": case["name"],
            "steps": steps
        }
    
        # 4) Init Healenium manager
        print(f"Init Healenium at {HEALENIUM_HOST}")
        manager = HealingManager(
            db_config_kb=DB_CONFIG,
            db_config_reporting=DB_CONFIG,
            healenium_host=HEALENIUM_HOST,
            visual_baseline_dir="visual_baseline"
        )
        manager.enable_python_fallback = True
    
        # 5) Init Selenium Remote
        print(f"Init Selenium at {SELENIUM_HOST}")
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
    
        driver = webdriver.Remote(
            command_executor=SELENIUM_HOST,
            options=chrome_options,
        )
    
        # 6) Gọi test runner
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
        # IN LỖI RA LOG DOCKER
        print("========== ERROR ============")
        traceback.print_exc()
        print("=============================")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

    finally:
        if driver: driver.quit()
        if manager: manager.close()
        if cur: cur.close()
        if conn: conn.close()

    return {
        "test_case_id": test_case_id,
        "test_case_name": case["name"],
        "status": status,
        "steps": len(steps)
    }

import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)