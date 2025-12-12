# File: evaluation/confidence_scorer.py
# Chức năng: F06 - Đánh giá độ tin cậy
# Ngôn ngữ & Công nghệ: Python
# Mục đích: Tính toán điểm tin cậy và phân loại kết quả cuối cùng.

from statistics import mean
from proactive_fault_prevention.config import SCORE_PASS_THRESHOLD, SCORE_WARN_THRESHOLD

def calculate_score(match_details, test_results):
    """
    - Nếu runner ERROR -> ("ERROR", 0)
    - Nếu có test FAIL -> ("FAIL", 0)
    - Ngược lại:
        pass_rate = passed / total (nếu total=0 → 1.0)
        match_strength = avg(score) từ match_details (0 nếu rỗng)
        final_score = 0.6*match_strength + 0.4*(pass_rate*100)
      Map ngưỡng:
        PASS >= SCORE_PASS_THRESHOLD
        WARN >= SCORE_WARN_THRESHOLD
        else FAIL
    """
    tr = test_results or {}
    tr_status = tr.get("status")

    if tr_status == "ERROR":
        return "ERROR", 0.0

    passed = int(tr.get("passed", 0) or 0)
    failed = int(tr.get("failed", 0) or 0)
    total  = int(tr.get("total", 0) or 0)

    if failed > 0:
        return "FAIL", 0.0

    scores = [float(m.get("score", 0)) for m in (match_details or [])
              if isinstance(m.get("score", None), (int, float))]
    match_strength = mean(scores) if scores else 0.0
    pass_rate = (passed / total) if total > 0 else 1.0

    final_score = 0.6 * match_strength + 0.4 * (pass_rate * 100.0)

    if final_score >= SCORE_PASS_THRESHOLD:
        status = "PASS"
    elif final_score >= SCORE_WARN_THRESHOLD:
        status = "WARN"
    else:
        status = "FAIL"

    return status, round(final_score, 2)
