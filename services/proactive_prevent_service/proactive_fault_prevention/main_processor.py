# File: proactive_fault_prevention/main_processor.py
import os
import traceback
from datetime import datetime, timezone, timedelta
from proactive_fault_prevention.analyzers import git_analyzer, locator_scanner, impact_analyzer
from proactive_fault_prevention.execution import test_executor 
from proactive_fault_prevention.evaluation import confidence_scorer
from shared.persistence import database_handler

# --- CẤU HÌNH TIMEZONE HÀ NỘI ---
HN_TZ = timezone(timedelta(hours=7))

def make_ts_hanoi() -> str:
    """Tạo timestamp định dạng ISO cho Hà Nội."""
    return datetime.now(HN_TZ).isoformat(timespec="seconds")

def process_analysis_request(request_data: dict):
    """
    Luồng xử lý chính: Git Diff -> Predict -> Save Predicted -> Execute -> Score -> Update Knowledge.
    """
    # 1. Trích xuất metadata ban đầu từ Request
    git_url = request_data.get("git_url")
    head_sha = request_data.get("head_sha")
    base_sha = request_data.get("base_sha")
    project_id = request_data.get("project_id", "default_project")
    
    testcase_info = request_data.get("testcase", {})
    steps_data = testcase_info.get("steps", [])
    tc_name = testcase_info.get("test_name") or f"Case_{request_data.get('case_id', 'Unknown')}"
    
    repo_name = git_url.split('/')[-1].replace('.git', '') if git_url else "unknown"
    start_time = make_ts_hanoi()
    
    # Khởi tạo Object kết quả để lưu MongoDB
    analysis_result = {
        "pr": {
            "repo_full_name": request_data.get("repo_full_name", f"user/{repo_name}"),
            "clone_url": git_url,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "received_at": start_time,
            "project_id": project_id,
            "case_id": request_data.get("case_id")
        },
        "status": "IN_PROGRESS",
        "timestamps": {"start": start_time}
    }

    try:
        # ============ STEP 1: Git Diff Analysis (F01/F02) ============
        print(f"INFO: [F02] Analyzing Git Diff for {repo_name}...")
        ui_changes, commit_metadata = git_analyzer.analyze_diff(git_url, head_sha, base_sha)
        
        analysis_result["pr"].update(commit_metadata)
        analysis_result["ui_changes"] = ui_changes
        analysis_result["timestamps"]["after_diff"] = make_ts_hanoi()

        # ============ STEP 2: Build Locator Inventory ============
        locator_inventory = []
        if steps_data:
            print(f"INFO: Extracting locators from DB steps for: {tc_name}")
            locator_inventory = locator_scanner.extract_locators_from_steps(steps_data, tc_name)
        analysis_result["timestamps"]["after_scan"] = make_ts_hanoi()

        # ============ STEP 3: Predict Impact (F03/F04) ============
        print(f"INFO: [F03] Predicting UI Impact...")
        predictions = impact_analyzer.predict_impact(ui_changes, locator_inventory)
        impacted_locators = predictions.get('impacted_locators', [])
        
        analysis_result["analysis_details"] = {
            "predicted_impact": len(impacted_locators) > 0,
            "match_details": predictions.get('match_details', []),
            "impacted_locators": impacted_locators
        }
        analysis_result["timestamps"]["after_predict"] = make_ts_hanoi()

        # --- [MỚI] CHIẾN THUẬT LƯU SỚM: Lưu ngay khi dự báo (PREDICTED) ---
        if impacted_locators:
            print(f"INFO: [F08] Saving {len(impacted_locators)} predicted locators to PostgreSQL...")
            for loc in impacted_locators:
                loc['project_id'] = project_id
                database_handler.upsert_proactive_healing_knowledge(
                    loc_data=loc,
                    confidence_score=0, # Chưa có điểm tin cậy thực tế
                    commit_metadata=analysis_result["pr"],
                    repair_ms=0,
                    source_type='PREDICTED' # Nhãn dự đoán
                )

        # ============ STEP 4: Execute Smoke Test (F05) ============
        if impacted_locators:
            print(f"INFO: [F05] Executing direct smoke test for: {tc_name}")
            test_results = test_executor.run_steps_directly(steps_data, tc_name)
        else:
            test_results = {"status": "PASS", "passed": 0, "failed": 0, "total": 0, "note": "No impact predicted."}

        analysis_result["test_result"] = test_results
        analysis_result["timestamps"]["after_execute"] = make_ts_hanoi()

        # ============ STEP 5: Score Confidence (F06) ============
        print(f"INFO: [F06] Calculating confidence score...")
        status, score, rationale = confidence_scorer.calculate_score(
            match_details=analysis_result["analysis_details"]["match_details"],
            impacted_locators=impacted_locators,
            test_results=test_results
        )
        
        # Tính toán thời gian sửa lỗi (repair_ms)
        try:
            t_start = datetime.fromisoformat(analysis_result["timestamps"]["start"])
            t_now = datetime.fromisoformat(make_ts_hanoi())
            repair_ms = int((t_now - t_start).total_seconds() * 1000)
        except: repair_ms = 0

        analysis_result["status"] = status
        analysis_result["confidence"] = {
            "status": status,
            "score": float(score),
            "rationale": rationale,
            "repair_duration_ms": repair_ms
        }
        analysis_result["timestamps"]["after_score"] = make_ts_hanoi()

        # ============ STEP 5.5: Update & Verify Knowledge (Postgres) ============
        # Nếu test FAIL đúng step dự báo và điểm > 75%, nâng cấp lên PROACTIVE (đã xác thực)
        if status in ["FAIL", "CONFIRMED_IMPACT"] and score >= 75:
            print(f"INFO: [F08] Confirming healing knowledge with score {score}%...")
            for loc in impacted_locators:
                loc['project_id'] = project_id
                database_handler.upsert_proactive_healing_knowledge(
                    loc_data=loc,
                    confidence_score=score,
                    commit_metadata=analysis_result["pr"],
                    repair_ms=repair_ms,
                    source_type='PROACTIVE' # Nhãn đã xác thực
                )
            analysis_result["confidence"]["knowledge_updated"] = True
        else:
            print(f"INFO: Step 5.5 skipped. Status: {status}, Score: {score}")
            analysis_result["confidence"]["knowledge_updated"] = False

    except Exception as e:
        print(f"CRITICAL ERROR in Pipeline: {e}")
        traceback.print_exc()
        analysis_result["status"] = "ERROR"
        analysis_result["error_message"] = str(e)

    # ============ STEP 6: Finalize & Save to MongoDB (F08) ============
    analysis_result["timestamps"]["end"] = make_ts_hanoi()
    try:
        saved_id = database_handler.save_analysis_result(analysis_result)
        if saved_id:
            analysis_result["_id"] = str(saved_id)
            print(f"SUCCESS: Analysis result saved to MongoDB. ID: {saved_id}")
    except Exception as db_e:
        print(f"ERROR saving to MongoDB: {db_e}")

    return analysis_result