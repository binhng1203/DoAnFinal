# File: execution/test_executor.py
# F05 - Thực thi targeted smoke test bằng pytest JSON report

import sys
import subprocess
import json
import os
from proactive_fault_prevention.config import TEST_EXECUTION_CONFIG

def _parse_json_report(report_path):
    """
    Parse file JSON do plugin pytest-json-report tạo.
    Trả về dict có status ∈ {PASS, FAIL, ERROR}.
    """
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)

        summary = report.get('summary', {}) or {}
        failed = int(summary.get('failed', 0) or 0)
        passed = int(summary.get('passed', 0) or 0)
        total  = int(summary.get('total', 0) or 0)

        failed_tests = []
        for test in report.get('tests', []) or []:
            if test.get('outcome') == 'failed':
                failed_tests.append({
                    'nodeid': test.get('nodeid'),
                    'setup_error': (test.get('setup') or {}).get('longrepr'),
                    'call_error': (test.get('call') or {}).get('longrepr'),
                    'teardown_error': (test.get('teardown') or {}).get('longrepr'),
                })

        status = "PASS" if failed == 0 else "FAIL"

        # đảm bảo total nhất quán
        calc_total = passed + failed
        if total < calc_total:
            total = calc_total

        return {
            "status": status,           # PASS | FAIL
            "passed": passed,
            "failed": failed,
            "total": total,
            "details": failed_tests
        }
    except FileNotFoundError:
        return {
            "status": "ERROR", "passed": 0, "failed": 0, "total": 0,
            "details": [{"error": f"report not found: {report_path}. "
                                   f"Is pytest-json-report installed?"}]
        }
    except json.JSONDecodeError:
        return {
            "status": "ERROR", "passed": 0, "failed": 0, "total": 0,
            "details": [{"error": "invalid json report"}]
        }

def run_targeted_tests(test_list):
    """
    Thực thi danh sách test case bằng pytest (JSON report).
    Trả về test_result với schema thống nhất: status ∈ {PASS, FAIL, ERROR}
    """
    if not test_list:
        return {
            "status": "PASS",   # không có test cần chạy → coi như pass
            "passed": 0,
            "failed": 0,
            "total": 0,
            "details": [],
            "runner": {"command": []}
        }

    report_file = TEST_EXECUTION_CONFIG.get('report_file', 'test_run_report.json')
    if os.path.exists(report_file):
        try:
            os.remove(report_file)
        except OSError:
            pass

    # Khử trùng lặp nodeid và giữ thứ tự ổn định
    unique_tests = []
    seen = set()
    for t in test_list:
        if t not in seen:
            seen.add(t)
            unique_tests.append(t)

    # Gọi pytest theo đúng interpreter hiện tại để tránh vấn đề PATH
    command = [sys.executable, "-m", "pytest"] + unique_tests + [
        "--json-report", f"--json-report-file={report_file}"
    ]
    print(f"Executing command: {' '.join(command)}")

    try:
        cp = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        # Python interpreter không hợp lệ (rất hiếm)
        return {
            "status": "ERROR",
            "passed": 0, "failed": 0, "total": 0,
            "details": [{"error": "python interpreter not found via sys.executable"}],
            "runner": {"command": command}
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "passed": 0, "failed": 0, "total": 0,
            "details": [{"error": f"unexpected runner error: {str(e)}"}],
            "runner": {"command": command}
        }

    # Dù exit code thế nào, vẫn parse JSON report nếu có
    parsed = _parse_json_report(report_file)
    parsed["runner"] = {"command": command, "returncode": cp.returncode}

    # Nếu parser báo ERROR và stderr có thông tin, thêm vào details để debug
    if parsed.get("status") == "ERROR":
        tail_err = (cp.stderr or "").strip()
        if tail_err:
            parsed.setdefault("details", []).append({"stderr_tail": tail_err[-400:]})
        # Gợi ý cài plugin nếu chưa có
        parsed.setdefault("details", []).append(
            {"hint": "Install plugin: pip install pytest-json-report"}
        )

    # Bảo đảm total nhất quán khi PASS/FAIL
    if parsed["status"] in ("PASS", "FAIL"):
        calc_total = parsed["passed"] + parsed["failed"]
        if parsed["total"] < calc_total:
            parsed["total"] = calc_total

    return parsed
