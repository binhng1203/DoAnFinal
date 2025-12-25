import git
import os
import re
from collections import defaultdict
from whatthepatch import parse_patch
from proactive_fault_prevention.config import REPO_CACHE_DIRECTORY, UI_FILE_EXTENSIONS, ATTRIBUTE_PATTERN

COMPILED_ATTRIBUTE_PATTERN = re.compile(ATTRIBUTE_PATTERN)

NOISE_PATTERNS = [
    r'^</.*>$', r'^>$', r'^<div.*>$', r'^\s*$', 
    r'^(import|export).*', r'^\{/\*.*\*/\}$', r'^//.*'
]
COMPILED_NOISE_PATTERNS = [re.compile(p) for p in NOISE_PATTERNS]

def get_repository(clone_url, cache_dir=REPO_CACHE_DIRECTORY):
    name = clone_url.split("/")[-1]
    repo_name = name[:-4] if name.endswith(".git") else name
    repo_path = os.path.join(cache_dir, repo_name)

    if os.path.exists(repo_path):
        repo = git.Repo(repo_path)
        for remote in repo.remotes:
            remote.fetch()
    else:
        os.makedirs(cache_dir, exist_ok=True)
        repo = git.Repo.clone_from(clone_url, repo_path)
    return repo

def is_noise(content):
    content = content.strip()
    return any(pattern.match(content) for pattern in COMPILED_NOISE_PATTERNS)

def analyze_diff(clone_url, head_sha, base_sha):
    """
    Phân tích diff và trả về: (ui_changes, commit_metadata)
    """
    changes_by_type = defaultdict(list)
    repo = get_repository(clone_url, REPO_CACHE_DIRECTORY)
    
    commit_head = repo.commit(head_sha)
    commit_base = repo.commit(base_sha)
    
    # --- [MỚI] Bóc tách thông tin Author và Commit ---
    commit_metadata = {
        "author_name": commit_head.author.name,
        "author_email": commit_head.author.email,
        "commit_message": commit_head.message.strip(),
        "committed_date": commit_head.committed_datetime.isoformat()
    }

    diff_index = commit_base.diff(commit_head)

    def pick_path(d):
        return d.b_path or d.a_path or ""

    def safe_int(val, default=1):
        try: return max(int(val), 1)
        except: return default

    for ctype in ('M', 'A', 'D', 'R'):
        for d in diff_index.iter_change_type(ctype):
            path_for_filter = pick_path(d)
            if not path_for_filter.endswith(UI_FILE_EXTENSIONS):
                continue

            raw = repo.git.diff(commit_base, commit_head, '--', path_for_filter)
            for patch in parse_patch(raw):
                if not getattr(patch, "changes", None):
                    continue

                for ch in patch.changes:
                    if ch.old is not None and ch.new is not None:
                        continue 
                    
                    line_content = str(getattr(ch, "line", "") or "").strip()
                    if is_noise(line_content):
                        continue

                    if ch.old is None:
                        change_type, ln = 'added', safe_int(ch.new)
                    elif ch.new is None:
                        change_type, ln = 'deleted', safe_int(ch.old)
                    else:
                        continue

                    matched = list(COMPILED_ATTRIBUTE_PATTERN.finditer(line_content))
                    if matched:
                        for m in matched:
                            changes_by_type[change_type].append({
                                'file_path': path_for_filter,
                                'line_num': ln,
                                'attribute_name': m.group(1),
                                'attribute_value': m.group(2)
                            })
                    elif len(line_content) > 1 and not line_content.startswith('<'):
                        changes_by_type[change_type].append({
                            'file_path': path_for_filter,
                            'line_num': ln,
                            'attribute_name': None,
                            'attribute_value': line_content
                        })
                        
    ui_changes = {k: changes_by_type.get(k, []) for k in ('added', 'deleted', 'modified')}
    
    # Trả về cả 2 thông tin
    return ui_changes, commit_metadata

def safe_changes_for_impact(changes_dict):
    all_changes = []
    if not isinstance(changes_dict, dict): return all_changes
    for ctype in ["added", "deleted", "modified"]:
        for item in changes_dict.get(ctype, []):
            all_changes.append({
                "file_path": str(item.get("file_path") or ""),
                "line_num": int(item.get("line_num") or 1),
                "change_type": ctype,
                "attribute_name": str(item.get("attribute_name") or ""),
                "attribute_value": str(item.get("attribute_value") or ""),
            })
    return all_changes