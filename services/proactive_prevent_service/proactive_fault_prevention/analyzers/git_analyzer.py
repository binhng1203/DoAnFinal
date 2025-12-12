# proactive_fault_prevention/analyzers/git_analyzer.py
import git
import os
import re
from collections import defaultdict
from whatthepatch import parse_patch
from proactive_fault_prevention.config import REPO_CACHE_DIRECTORY, UI_FILE_EXTENSIONS, ATTRIBUTE_PATTERN

COMPILED_ATTRIBUTE_PATTERN = re.compile(ATTRIBUTE_PATTERN)


def get_repository(clone_url, cache_dir=REPO_CACHE_DIRECTORY):
    """Lấy repo từ cache hoặc clone mới."""
    name = clone_url.split("/")[-1]
    repo_name = name[:-4] if name.endswith(".git") else name
    repo_path = os.path.join(cache_dir, repo_name)

    if os.path.exists(repo_path):
        print(f"[DEBUG] Repository '{repo_name}' found in cache. Fetching...")
        repo = git.Repo(repo_path)
        for remote in repo.remotes:
            remote.fetch()
    else:
        print(f"[DEBUG] Cloning repository '{repo_name}'...")
        os.makedirs(cache_dir, exist_ok=True)
        repo = git.Repo.clone_from(clone_url, repo_path)
    return repo


# def safe_int(val, default=1):
#     try:
#         v = int(val)
#         return max(v, 1)
#     except (TypeError, ValueError):
#         return default


from collections import defaultdict

def analyze_diff(clone_url, head_sha, base_sha):
    """
    Phân tích diff giữa base và head.
    Trả về dict theo loại change:
    {
        'added': [ {...}, {...}, ... ],
        'deleted': [ {...}, ... ],
        'modified': [ {...}, ... ]
    }
    Mỗi item là:
    {'file_path','line_num','attribute_name','attribute_value'}
    """
    changes_by_type = defaultdict(list)

    repo = get_repository(clone_url, REPO_CACHE_DIRECTORY)
    commit_head = repo.commit(head_sha)
    commit_base = repo.commit(base_sha)
    diff_index = commit_base.diff(commit_head)

    def pick_path(d):
        return d.b_path or d.a_path or ""

    def safe_int(val, default=1):
        try:
            v = int(val)
            return max(v, 1)
        except (TypeError, ValueError):
            return default

    for ctype in ('M', 'A', 'D', 'R'):
        for d in diff_index.iter_change_type(ctype):
            path_for_filter = pick_path(d)
            if not path_for_filter.endswith(UI_FILE_EXTENSIONS):
                continue

            print(f"[DEBUG] Diff type: {ctype}, file: {path_for_filter}")

            raw = repo.git.diff(commit_base, commit_head, '--', (d.a_path or d.b_path))
            for patch in parse_patch(raw):
                if not getattr(patch, "changes", None):
                    continue

                old_path = getattr(getattr(patch, "header", None), "old_path", None)
                new_path = getattr(getattr(patch, "header", None), "new_path", None)

                for ch in patch.changes:
                    # Xác định loại change
                    if ch.old is None and ch.new is not None:
                        change_type = 'added'
                        ln = safe_int(ch.new)
                        fp = str(new_path or path_for_filter)
                    elif ch.new is None and ch.old is not None:
                        change_type = 'deleted'
                        ln = safe_int(ch.old)
                        fp = str(old_path or path_for_filter)
                    else:
                        change_type = 'modified'
                        ln = safe_int(ch.new or ch.old)
                        fp = str(new_path or old_path or path_for_filter)

                    # Lấy nội dung dòng
                    line_content = str(getattr(ch, "line", "") or "").strip()
                    matched = list(COMPILED_ATTRIBUTE_PATTERN.finditer(line_content))

                    if matched:
                        for m in matched:
                            changes_by_type[change_type].append({
                                'file_path': fp,
                                'line_num': ln,
                                'attribute_name': str(m.group(1) or ""),
                                'attribute_value': str(m.group(2) or "")
                            })
                    else:
                        changes_by_type[change_type].append({
                            'file_path': fp,
                            'line_num': ln,
                            'attribute_name': None,
                            'attribute_value': line_content
                        })

    # Chuyển thành dict bình thường, đảm bảo các key tồn tại
    result = {k: changes_by_type.get(k, []) for k in ('added', 'deleted', 'modified')}
    print(f"[DEBUG] Total changes detected: added={len(result['added'])}, "
          f"deleted={len(result['deleted'])}, modified={len(result['modified'])}")
    return result

def safe_changes_for_impact(changes_dict):
    """
    Trả về list dict hợp lệ cho Predicting impact, đảm bảo không crash
    """
    all_changes = []
    if not isinstance(changes_dict, dict):
        return all_changes
    for ctype in ["added", "deleted", "modified"]:
        items = changes_dict.get(ctype, [])
        if not isinstance(items, list):
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            all_changes.append(
                {
                    "file_path": str(item.get("file_path") or ""),
                    "line_num": int(item.get("line_num") or 1),
                    "change_type": ctype,
                    "attribute_name": str(item.get("attribute_name") or ""),
                    "attribute_value": str(item.get("attribute_value") or ""),
                }
            )
    return all_changes
