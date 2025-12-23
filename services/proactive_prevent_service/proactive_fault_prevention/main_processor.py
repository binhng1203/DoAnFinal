# File: proactive_fault_prevention/main_processor.py
import os
from datetime import datetime, timezone, timedelta
from proactive_fault_prevention.analyzers import git_analyzer, locator_scanner, impact_analyzer
# Lưu ý: test_executor cũ chạy bằng pytest file path. 
# Nếu bạn không có file path, phần execute này sẽ cần xử lý riêng (tạm thời giữ nguyên hoặc skip).
from proactive_fault_prevention.execution import test_executor 
from proactive_fault_prevention.evaluation import confidence_scorer
from shared.persistence import database_handler

# --- TIMEZONE ---
HN_TZ = timezone(timedelta(hours=7))

def make_ts_hanoi() -> str:
    return datetime.now(HN_TZ).isoformat(timespec="seconds")

def process_analysis_request(request_data: dict):
    # 1. Trích xuất thông tin
    git_url = request_data.get("git_url")
    head_sha = request_data.get("head_sha")
    base_sha = request_data.get("base_sha")
    
    # Lấy thông tin testcase (bao gồm steps) được truyền từ API Server
    testcase_info = request_data.get("testcase", {})
    steps_data = testcase_info.get("steps", [])
    
    # Lấy tên repo
    repo_name = git_url.split('/')[-1].replace('.git', '') if git_url else "unknown"
    
    start_time = make_ts_hanoi()
    
    analysis_result = {
        "pr": {
            "repo_full_name": request_data.get("repo_full_name", f"user/{repo_name}"),
            "clone_url": git_url,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "received_at": start_time,
            "project_id": request_data.get("project_id"),
            "case_id": request_data.get("case_id")
        },
        "status": "IN_PROGRESS",
        "timestamps": {"start": start_time}
    }

    try:
        # ============ Step 1: Diff (Git Analyzer) ============
        print(f"INFO: Analyzing diff for {git_url}...")
        ui_changes = git_analyzer.analyze_diff(git_url, head_sha, base_sha)
        
        analysis_result["ui_changes"] = ui_changes
        analysis_result["timestamps"]["after_diff"] = make_ts_hanoi()

        # ============ Step 2: Build Locator Inventory (FROM DB STEPS) ============
        # [THAY ĐỔI Ở ĐÂY] Không quét file nữa, lấy trực tiếp từ steps
        if steps_data:
            print(f"INFO: Building locator inventory from {len(steps_data)} DB steps...")
            locator_inventory = locator_scanner.extract_locators_from_steps(steps_data)
        else:
            print("WARNING: No steps data provided in request. Inventory will be empty.")
            locator_inventory = []
            
        analysis_result["timestamps"]["after_scan"] = make_ts_hanoi()

        # ============ Step 3: Predict Impact ============
        # So khớp UI Changes (Git) với Locator Inventory (DB)
        predictions = impact_analyzer.predict_impact(ui_changes, locator_inventory)
        
        # Danh sách các step bị ảnh hưởng (Thay vì tên hàm test như trước)
        impacted_locators = predictions.get('impacted_locators', [])
        
        analysis_result["analysis_details"] = {
            "predicted_impact": len(impacted_locators) > 0,
            "match_details": predictions.get('match_details', []),
            "impacted_locators": impacted_locators
        }
        analysis_result["timestamps"]["after_predict"] = make_ts_hanoi()

        # ============ Step 4: Execute Test ============
        # [LƯU Ý QUAN TRỌNG]
        # Hệ thống cũ dùng 'pytest' chạy file. Hệ thống mới dùng DB steps.
        # Ở đây ta tạm thời SKIP phần chạy test nếu không có cơ chế chạy từ DB trong service này.
        # Hoặc bạn có thể gọi API /run_testcase của service kia để chạy kiểm chứng.
        
        # Ở đây tôi giả lập kết quả chạy test là SKIPPED để tập trung vào phân tích.
        test_results = {
            "status": "SKIPPED", 
            "note": "Execution skipped. Using DB-based analysis only."
        }
        
        # Nếu vẫn muốn chạy test, bạn cần tích hợp việc gọi sang endpoint /run_testcase
        # mà chúng ta đã bàn ở các prompt trước.
        
        analysis_result["test_result"] = test_results
        analysis_result["timestamps"]["after_execute"] = make_ts_hanoi()

        # ============ Step 5: Score Confidence ============
        # Tính điểm dựa trên mức độ khớp (Fuzzy Match Score)
        status, score = confidence_scorer.calculate_score(
            match_details=analysis_result["analysis_details"]["match_details"],
            test_results=test_results, # Lưu ý: nếu skipped thì điểm sẽ phụ thuộc hoàn toàn vào Match Score
        )
        
        analysis_result["status"] = status
        analysis_result["confidence"] = {
            "status": status,
            "score": float(score),
            "rationale": f"Analysis based on DB steps. Score: {score}"
        }
        analysis_result["timestamps"]["after_score"] = make_ts_hanoi()

    except Exception as e:
        msg = f"An error occurred during analysis: {e}"
        print(f"ERROR: {msg}")
        import traceback
        traceback.print_exc()
        analysis_result["status"] = "ERROR"
        analysis_result["error_message"] = str(e)

    # ============ Step 6: Save & Return ============
    analysis_result["timestamps"]["end"] = make_ts_hanoi()
    
    try:
        print("INFO: Saving analysis result to MongoDB...")
        saved_id = database_handler.save_analysis_result(analysis_result)
        
        # [FIX QUAN TRỌNG]
        # PyMongo tự động thêm _id (dạng ObjectId) vào dict input.
        # Ta cần convert nó sang string để Flask không bị lỗi JSON.
        if saved_id:
            # Convert ObjectId sang string
            if "_id" in analysis_result:
                analysis_result["_id"] = str(analysis_result["_id"])
            
            print(f"INFO: Saved successfully to DB. ID: {analysis_result.get('_id')}")
        else:
            # Nếu saved_id là None -> Lỗi
            print("ERROR: Failed to save result to MongoDB (Connection Error).")
            # Xóa _id ảo do PyMongo tự tạo để tránh gây hiểu lầm ở API response
            if "_id" in analysis_result:
                del analysis_result["_id"]

    except Exception as e:
        print(f"CRITICAL ERROR saving to DB: {e}")
        import traceback
        traceback.print_exc()
        # Nếu lỗi lưu DB, vẫn trả về kết quả phân tích nhưng kèm thông báo lỗi
        analysis_result["db_error"] = str(e)

    return analysis_result