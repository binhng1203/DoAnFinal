import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import tuyệt đối để chạy ổn định trong Docker
from runner.db_loader import fetch_test_case_data
from runner.generic_executor import execute_test_logic

app = FastAPI()
logger = logging.getLogger(__name__)

class RunRequest(BaseModel):
    test_case_id: int

@app.post("/run_testcase")
def run_testcase(req: RunRequest):
    """
    Endpoint chạy test đồng bộ. 
    API sẽ treo kết nối cho đến khi Selenium hoàn thành hoặc lỗi.
    """
    test_case_id = req.test_case_id
    
    # 1. Cấu hình Database từ môi trường Docker
    db_config = {
        "host": os.environ.get("DB_HOST", "system_db"),
        "dbname": "final",
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", "postgres"),
        "port": 5432
    }
    
    # 2. Lấy dữ liệu kịch bản từ schema management
    case, steps = fetch_test_case_data(test_case_id, db_config)
    if not case:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy Test Case ID {test_case_id}")

    logger.info(f">>> Bắt đầu thực thi Test Case: {case['name']}")

    # 3. Gọi thực thi đồng bộ và đợi kết quả
    result = execute_test_logic(case, steps, db_config)

    # 4. Trả về response cuối cùng dựa trên kết quả chạy thật
    if result["status"] == "passed":
        return {
            "test_case_id": test_case_id,
            "test_name": case["name"],
            "status": "passed",
            "steps_executed": len(steps),
            "message": "Kiểm thử hoàn thành thành công."
        }
    else:
        return {
            "test_case_id": test_case_id,
            "test_name": case["name"],
            "status": "failed",
            "error": result.get("error"),
            "message": "Kiểm thử thất bại."
        }