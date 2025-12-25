# File: evaluation/confidence_scorer.py
from statistics import mean
from proactive_fault_prevention.config import SCORE_PASS_THRESHOLD, SCORE_WARN_THRESHOLD

def calculate_score(match_details, impacted_locators, test_results):
    """
    F06: Tính toán độ tin cậy dựa trên sự khớp nhau giữa dự báo và thực tế.
    """
    tr = test_results or {}
    tr_status = tr.get("status")

    # 1. Trường hợp Runner gặp lỗi hệ thống
    if tr_status == "ERROR":
        return "ERROR", 0.0, "Execution engine error. Cannot verify prediction."

    # 2. Lấy dữ liệu thực tế từ bài test
    failed_count = int(tr.get("failed", 0) or 0)
    details = tr.get("details", [])
    # Lấy step bị fail thực tế (ví dụ: step 3)
    actual_failed_step = details[0].get("failed_at_step") if details else None

    # 3. Lấy dữ liệu từ dự báo (Match Score)
    scores = [float(m.get("score", 0)) for m in (match_details or [])]
    match_strength = mean(scores) if scores else 0.0
    
    # Lấy danh sách các step mà chúng ta đã dự báo là sẽ hỏng
    predicted_steps = [loc.get("step_order") for loc in (impacted_locators or [])]

    # --- LOGIC ĐÁNH GIÁ ĐỘ TIN CẬY ---

    # TRƯỜNG HỢP A: Test THẤT BẠI (FAIL)
    if failed_count > 0:
        # Nếu hỏng đúng step đã dự báo -> Hệ thống cực kỳ tin cậy (Confirm được lỗi)
        if actual_failed_step in predicted_steps:
            final_score = match_strength
            status = "FAIL"
            rationale = f"Prediction confirmed! Test failed at predicted step {actual_failed_step}. Match score: {match_strength}%."
        else:
            # Hỏng nhưng không đúng step dự báo -> Độ tin cậy thấp
            final_score = 0.0
            status = "FAIL"
            rationale = f"Test failed at step {actual_failed_step}, but we predicted impact on steps {predicted_steps}."

    # TRƯỜNG HỢP B: Test VƯỢT QUA (PASS)
    else:
        if match_strength > 0:
            # Dự báo hỏng nhưng lại PASS -> Dương tính giả (False Positive)
            final_score = max(0, 100 - match_strength) 
            status = "WARN"
            rationale = "False Positive: Predicted impact, but test passed. Possible backup locators exist."
        else:
            # Không dự báo hỏng và thực tế PASS -> Tin cậy tuyệt đối
            final_score = 100.0
            status = "PASS"
            rationale = "No impact predicted and test passed successfully."

    # Kiểm tra lại ngưỡng để gán nhãn Status cuối cùng (Nếu không phải FAIL)
    if status != "FAIL":
        if final_score >= SCORE_PASS_THRESHOLD:
            status = "PASS"
        elif final_score >= SCORE_WARN_THRESHOLD:
            status = "WARN"
        else:
            status = "FAIL"

    return status, round(final_score, 2), rationale