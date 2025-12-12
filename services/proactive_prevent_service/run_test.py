# run_test.py
import os
import shutil
import sys
from pathlib import Path
import git
import requests
import urllib.parse

# Thêm proactive_fault_prevention và shared vào sys.path
sys.path.insert(0, os.path.abspath("."))

from proactive_fault_prevention.main_processor import process_pull_request

# ===============================================
# === USER INPUT: Git URL, HEAD SHA, BASE SHA ===
# ===============================================
GIT_URL = "https://github.com/24thg12/minimal-shop"  # Thay bằng repo muốn test
HEAD_SHA = "1054af4"
BASE_SHA = "e23a456"

# Thư mục tạm clone repo
TMP_DIR = Path("./tmp_repo")

# ===============================================
# === 1) CLONE OR FETCH REPO
# ===============================================
if TMP_DIR.exists():
    print(f"Repo already exists at {TMP_DIR}, fetching latest...")
    repo = git.Repo(TMP_DIR)
    repo.remotes.origin.fetch()
else:
    print(f"Cloning repo {GIT_URL} into {TMP_DIR}...")
    repo = git.Repo.clone_from(GIT_URL, TMP_DIR)

# Lấy HEAD commit và base commit
try:
    head_commit = repo.commit(HEAD_SHA)
    base_commit = repo.commit(BASE_SHA)
except Exception as e:
    raise RuntimeError(f"Cannot find HEAD or BASE commit: {e}")

AUTHOR_NAME = head_commit.author.name or "unknown-author"
AUTHOR_EMAIL = head_commit.author.email or ""

REMOTE_URL = GIT_URL
repo_name = TMP_DIR.name
repo_full_name = repo_name  # fallback

# ===============================================
# === 2) HELPERS PARSE REMOTE
# ===============================================
def _parse_github_owner_repo(url: str):
    if not url or "github.com" not in url:
        return None, None
    m = git_pattern = r".*github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$"
    import re
    m = re.match(git_pattern, url)
    if m:
        return m.group("owner"), m.group("repo")
    return None, None

def _parse_gitlab_owner_repo(url: str):
    if not url or "gitlab.com" not in url:
        return None, None
    import re
    m = re.match(r".*gitlab\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", url)
    if m:
        return m.group("owner"), m.group("repo")
    return None, None

# ===============================================
# === 3) AUTODETECT PR/MR NUMBER
# ===============================================
def get_github_pr_number(owner: str, repo_name: str, sha: str) -> int | None:
    token = os.getenv("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{owner}/{repo_name}/commits/{sha}/pulls"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("number")
        else:
            print(f"WARNING: GitHub API status {resp.status_code}")
    except Exception as e:
        print(f"WARNING: GitHub API error: {e}")
    return None

def get_gitlab_mr_number(owner: str, repo_name: str, sha: str) -> int | None:
    token = os.getenv("GITLAB_TOKEN")
    proj = urllib.parse.quote_plus(f"{owner}/{repo_name}")
    url = f"https://gitlab.com/api/v4/projects/{proj}/repository/commits/{sha}/merge_requests"
    headers = {}
    if token:
        headers["PRIVATE-TOKEN"] = token
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("iid")
        else:
            print(f"WARNING: GitLab API status {resp.status_code}")
    except Exception as e:
        print(f"WARNING: GitLab API error: {e}")
    return None

def autodetect_pr_number(remote_url: str, sha: str) -> int | None:
    owner, repo_name = _parse_github_owner_repo(remote_url)
    if owner and repo_name:
        return get_github_pr_number(owner, repo_name, sha)
    owner, repo_name = _parse_gitlab_owner_repo(remote_url)
    if owner and repo_name:
        return get_gitlab_mr_number(owner, repo_name, sha)
    return None

AUTO_PR_NUMBER = autodetect_pr_number(REMOTE_URL, HEAD_SHA)

# ===============================================
# === 4) BUILD PAYLOAD
# ===============================================
# Tạo payload giả lập webhook
mock_payload = {
    "action": "opened",
    "repository": {
        "full_name": repo_full_name,
        "clone_url": REMOTE_URL,
    },
    "pull_request": {
        "user": {"login": AUTHOR_NAME},
        "head": {"sha": HEAD_SHA},
        "base": {"sha": BASE_SHA}
    }
}
if AUTO_PR_NUMBER is not None:
    mock_payload["number"] = AUTO_PR_NUMBER

# ===============================================
# === 5) RUN ANALYSIS
# ===============================================
if __name__ == "__main__":
    print("--- STARTING SMART ANALYSIS (Auto PR Number) ---")
    print(f"Repo: {repo_full_name}")
    print(f"Author: {AUTHOR_NAME} ({AUTHOR_EMAIL})")
    print(f"HEAD SHA: {HEAD_SHA}, BASE SHA: {BASE_SHA}")
    print(f"Remote URL: {REMOTE_URL}")
    print(f"PR number: {AUTO_PR_NUMBER if AUTO_PR_NUMBER else '(unknown)'}")
    print("------------------------------------------------")

    process_pull_request(mock_payload)

    print("--- ANALYSIS PROCESS FINISHED ---")
