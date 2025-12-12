# File: main_processor.py
# Chức năng: Orchestrator luồng F01→F08
# - Lấy thông tin PR/MR chuẩn (repo_name, repo_full_name, author, sha, clone_url)
# - Chạy phân tích diff, quét locator, dự đoán testcase, thực thi smoke test, chấm điểm
# - Lưu kết quả vào DB với timestamps theo giờ Hà Nội (UTC+7)
# - MỚI: Lưu email author dạng ẩn domain (vd: user@***.com)

import re
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from typing import Optional

# --- TIMEZONE: Asia/Bangkok (UTC+7) ---
try:
    from zoneinfo import ZoneInfo
    try:
        HN_TZ = ZoneInfo("Asia/Bangkok")
    except Exception:
        print("WARNING: 'Asia/Bangkok' timezone not found. Using manual UTC+7 offset.")
        HN_TZ = timezone(timedelta(hours=7))
except ImportError:
    print("WARNING: zoneinfo not available. Using UTC+7 manual offset.")
    HN_TZ = timezone(timedelta(hours=7))

# --- MODULE IMPORTS ---
from proactive_fault_prevention.analyzers import git_analyzer, locator_scanner, impact_analyzer
from proactive_fault_prevention.execution import test_executor
from proactive_fault_prevention.evaluation import confidence_scorer
from shared.persistence import database_handler


# =========================
#      TIME HELPERS
# =========================
def make_ts_hanoi() -> str:
    """Trả về timestamp ISO 8601 theo giờ Hà Nội, có offset +07:00."""
    return datetime.now(HN_TZ).isoformat(timespec="seconds")

def now_utc_iso() -> str:
    """Timestamp UTC ISO 8601 (nếu cần lưu song song)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# =========================
#   PAYLOAD META HELPERS
# =========================
def _derive_repo_name_from_clone_url(clone_url: str) -> str:
    """Suy ra repo_name từ clone_url (https/ssh/file), bỏ .git ở cuối."""
    if not clone_url:
        return "unknown-repo"
    p = urlparse(clone_url)
    tail = (p.path or "").rstrip("/").split("/")[-1]
    return re.sub(r"\.git$", "", tail) or "unknown-repo"

def _derive_full_name_from_clone_url(clone_url: str) -> Optional[str]:
    """
    Suy luận 'owner/name' từ clone_url nếu payload không có:
    - https://github.com/owner/name(.git)
    - ssh://git@github.com/owner/name(.git)
    - file:///D:/.../name (không có owner ⇒ trả None)
    """
    if not clone_url:
        return None
    p = urlparse(clone_url)
    parts = [seg for seg in (p.path or "").split("/") if seg]
    if len(parts) >= 2:
        owner, name = parts[-2], re.sub(r"\.git$", "", parts[-1])
        return f"{owner}/{name}"
    return None

def extract_pr_meta(payload: dict) -> dict:
    """Chuẩn hoá metadata cho GitHub/GitLab hoặc local."""
    repo = payload.get("repository", {}) or payload.get("project", {}) or {}
    pr   = payload.get("pull_request", {}) or payload.get("merge_request", {}) or {}
    obj  = payload.get("object_attributes", {})  # GitLab MR fields

    clone_url = (
        repo.get("clone_url") or
        repo.get("git_http_url") or
        repo.get("http_url") or
        repo.get("git_url") or
        payload.get("repo_clone_url")
    )

    # repo_full_name: ưu tiên repository.full_name / path_with_namespace; rồi tới PR base/head
    repo_full_name = (
        repo.get("full_name") or
        repo.get("path_with_namespace") or
        pr.get("base", {}).get("repo", {}).get("full_name") or
        pr.get("head", {}).get("repo", {}).get("full_name")
    )
    # nếu vẫn chưa có, thử ghép owner/name
    if not repo_full_name:
        owner_login = (repo.get("owner") or {}).get("login")
        name_only   = repo.get("name")
        if owner_login and name_only:
            repo_full_name = f"{owner_login}/{name_only}"
    # nếu vẫn chưa có nữa, suy ra từ clone_url
    if not repo_full_name:
        repo_full_name = _derive_full_name_from_clone_url(clone_url)

    repo_name = (
        repo.get("name") or
        repo.get("path") or
        _derive_repo_name_from_clone_url(clone_url)
    )

    pr_number = (
        payload.get("number") or
        pr.get("number") or
        obj.get("iid")
    )

    head_sha = (
        pr.get("head", {}).get("sha") or
        obj.get("last_commit", {}).get("id") or
        payload.get("after")
    )
    base_sha = (
        pr.get("base", {}).get("sha") or
        payload.get("before")
    )

    return {
        "repo_full_name": repo_full_name,
        "repo_name": repo_name,
        "clone_url": clone_url,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "base_sha": base_sha,
    }


# =========================
#      AUTHOR HELPERS
# =========================
def _author_from_git(commit_sha: Optional[str], clone_url: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Fallback: đọc trực tiếp metadata commit từ repo (GitPython).
    Trả về (author_name, author_email).
    """
    if not clone_url or not commit_sha:
        return None, None
    try:
        # dùng git_analyzer.get_repository để tái sử dụng cache
        repo = git_analyzer.get_repository(clone_url, git_analyzer.REPO_CACHE_DIRECTORY)
        c = repo.commit(commit_sha)
        # name & email là chắc chắn có trên commit
        name = getattr(c.author, "username", None) or c.author.name
        email = c.author.email
        return name, email
    except Exception:
        return None, None

def extract_author(payload: dict) -> str:
    """Lấy author chuẩn theo loại webhook (GitHub, GitLab, local)."""
    # GitHub PR
    author = payload.get("pull_request", {}).get("user", {}).get("login")
    if author:
        return author

    # GitHub: head repo owner (khi user ở head fork)
    author = payload.get("pull_request", {}).get("head", {}).get("repo", {}).get("owner", {}).get("login")
    if author:
        return author

    # GitHub push / sender
    author = payload.get("sender", {}).get("login") or payload.get("pusher", {}).get("name")
    if author:
        return author

    # GitLab MR
    author = payload.get("user", {}).get("username")
    if author:
        return author

    # Từ commits (sự kiện push)
    commits = payload.get("commits") or []
    if commits:
        a = commits[0].get("author", {}) or {}
        author = a.get("username") or a.get("name") or a.get("email")
        if author:
            return author

    # Fallback cuối: đọc từ Git commit
    meta = extract_pr_meta(payload)
    name, _ = _author_from_git(meta.get("head_sha"), meta.get("clone_url"))
    return name or "unknown-author"

def mask_email(email: Optional[str]) -> Optional[str]:
    """
    Ẩn domain của email: local@***.tld
    - 'user@example.com' -> 'user@***.com'
    - 'user@intra.local' -> 'user@***.local'
    - nếu email không hợp lệ hoặc None, trả về nguyên giá trị.
    """
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if "." in domain:
        parts = domain.split(".")
        tld = parts[-1]
        return f"{local}@***.{tld}"
    else:
        return f"{local}@***"

def extract_author_email(payload: dict) -> Optional[str]:
    """
    Lấy email author từ payload (nếu có) hoặc từ commit HEAD (fallback),
    sau đó trả về BẢN ĐÃ ẨN DOMAIN.
    """
    # GitHub PR (ít khi có), GitLab đôi khi có trong user/email
    email = payload.get("pull_request", {}).get("user", {}).get("email")
    if email:
        return mask_email(email)

    # Từ commits (push event)
    commits = payload.get("commits") or []
    if commits:
        a = commits[0].get("author", {}) or {}
        email = a.get("email")
        if email:
            return mask_email(email)

    # Fallback: đọc từ Git commit thật
    meta = extract_pr_meta(payload)
    _, email = _author_from_git(meta.get("head_sha"), meta.get("clone_url"))
    return mask_email(email)


# =========================
#     MAIN ORCHESTRATOR
# =========================
def process_pull_request(payload: dict):
    """
    Luồng chính: F01→F08
    - Lấy meta (repo_name, repo_full_name, author, email, sha, clone_url)
    - Diff UI → Scan locators → Predict → Execute → Score → Save
    - Ghi timestamps theo giờ Hà Nội (UTC+7)
    """
    # --- Meta & PR info ---
    meta = extract_pr_meta(payload)
    author = extract_author(payload)
    author_email_masked = extract_author_email(payload)

    repo_full_name = meta.get("repo_full_name")
    repo_name = meta.get("repo_name")
    repo_clone_url = meta.get("clone_url")
    pr_number = meta.get("pr_number")
    head_sha = meta.get("head_sha")
    base_sha = meta.get("base_sha")

    received_at = make_ts_hanoi()

    print(f"INFO: Starting analysis for PR #{pr_number if pr_number is not None else '(unknown)'} "
          f"by {author} (SHA: {str(head_sha)[:7] if head_sha else 'unknown'})")

    # --- Khởi tạo khung kết quả ---
    analysis_result = {
        "pr": {
            "repo_full_name": repo_full_name or repo_name,
            "repo_name": repo_name,
            "clone_url": repo_clone_url,
            "number": pr_number,
            "author": author,
            "author_email": author_email_masked,
            "head_sha": head_sha,
            "base_sha": base_sha,
            "received_at": received_at,
        },
        "status": "IN_PROGRESS",
        "timestamps": {"start": received_at}
    }

    try:
        # ============ Step 1/6: Diff ============
        print("INFO: Step 1/6 - Analyzing git diff...")
        ui_changes = git_analyzer.analyze_diff(repo_clone_url, head_sha, base_sha)
        analysis_result["ui_changes"] = ui_changes
        analysis_result["timestamps"]["after_diff"] = make_ts_hanoi()

        # ============ Step 2/6: Scan locators ============
        print("INFO: Step 2/6 - Scanning for locators...")
        locator_inventory = locator_scanner.scan_for_locators()
        analysis_result["timestamps"]["after_scan"] = make_ts_hanoi()

        # ============ Step 3/6: Predict impact ============
        print("INFO: Step 3/6 - Predicting impact...")
        predictions = impact_analyzer.predict_impact(ui_changes, locator_inventory)
        predicted_tests = sorted(set(predictions.get('predicted_failed_tests', [])))

        analysis_result["analysis_details"] = {
            "predicted_failed_tests": predicted_tests,
            "match_details": predictions.get('match_details', []),
            "impacted_locators": predictions.get('impacted_locators', [])
        }
        analysis_result["timestamps"]["after_predict"] = make_ts_hanoi()

        # Early PASS nếu không có test cần chạy
        if not predicted_tests:
            print("INFO: No test cases predicted to fail. Analysis complete.")
            analysis_result["test_result"] = {
                "status": "PASS",
                "passed": 0, "failed": 0, "total": 0,
                "details": []
            }
            analysis_result["status"] = "PASS"
            analysis_result["confidence"] = {
                "status": "PASS",
                "score": 100.0,
                "thresholds": {"warn": 75, "pass": 90},
                "rationale": "No impacted tests predicted"
            }
            analysis_result["timestamps"]["after_score"] = make_ts_hanoi()
            analysis_result["timestamps"]["end"] = make_ts_hanoi()
            database_handler.save_analysis_result(analysis_result)
            print(f"SUCCESS: Analysis complete for PR #{pr_number if pr_number is not None else '(unknown)'}."
                  f" Final status: PASS")
            return

        # ============ Step 4/6: Execute targeted tests ============
        print(f"INFO: Step 4/6 - Executing {len(predicted_tests)} targeted tests...")
        test_results = test_executor.run_targeted_tests(predicted_tests)
        analysis_result["test_result"] = test_results
        analysis_result["timestamps"]["after_execute"] = make_ts_hanoi()

        # ============ Step 5/6: Score ============
        print("INFO: Step 5/6 - Scoring confidence...")
        status, score = confidence_scorer.calculate_score(
            match_details=analysis_result["analysis_details"]["match_details"],
            test_results=test_results,
        )
        analysis_result["status"] = status
        analysis_result["confidence"] = {
            "status": status,
            "score": float(score),
            "thresholds": {"warn": 75, "pass": 90},
            "rationale": (
                "Fail detected" if status == "FAIL"
                else ("Runner error" if status == "ERROR"
                      else f"Blended score from match & pass-rate = {score}")
            ),
        }
        analysis_result["timestamps"]["after_score"] = make_ts_hanoi()

        # ============ Step 6/6: Save ============
        print("INFO: Step 6/6 - Saving final result...")
        analysis_result["timestamps"]["end"] = make_ts_hanoi()
        database_handler.save_analysis_result(analysis_result)
        print(f"SUCCESS: Analysis complete for PR #{pr_number if pr_number is not None else '(unknown)'}."
              f" Final status: {status}")

    except Exception as e:
        msg = f"An error occurred during analysis for PR #{pr_number if pr_number is not None else '(unknown)'}: {e}"
        print(f"ERROR: {msg}")
        analysis_result["status"] = "ERROR"
        analysis_result.setdefault("errors", []).append(str(e))
        analysis_result["timestamps"]["end"] = make_ts_hanoi()
        database_handler.save_analysis_result(analysis_result)
