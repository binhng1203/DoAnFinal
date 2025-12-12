import git
import os
import re
from whatthepatch import parse_patch
from proactive_fault_prevention.config import REPO_CACHE_DIRECTORY, UI_FILE_EXTENSIONS, ATTRIBUTE_PATTERN

COMPILED_ATTRIBUTE_PATTERN = re.compile(ATTRIBUTE_PATTERN)

def get_repository(clone_url, cache_dir):
    name = clone_url.split('/')[-1]
    # Python 3.9+: repo_name = name.removesuffix('.git')
    repo_name = name[:-4] if name.endswith('.git') else name  # tránh lỗi rstrip
    repo_path = os.path.join(cache_dir, repo_name)

    if os.path.exists(repo_path):
        print(f"Repository '{repo_name}' found in cache. Fetching...")
        repo = git.Repo(repo_path)
        for remote in repo.remotes:
            remote.fetch()
    else:
        print(f"Cloning repository '{repo_name}'...")
        os.makedirs(cache_dir, exist_ok=True)
        repo = git.Repo.clone_from(clone_url, repo_path)
    return repo

# replace your analyze_diff with this version (giữ nguyên imports & COMPILED_ATTRIBUTE_PATTERN)

def analyze_diff(clone_url, head_sha, base_sha):
    """
    Trả về danh sách thay đổi UI:
    [{'file_path','line_num','change_type','attribute_name','attribute_value'}]
    """
    from whatthepatch import parse_patch
    import re, os, git
    changed_attributes = []

    repo = get_repository(clone_url, REPO_CACHE_DIRECTORY)
    commit_head = repo.commit(head_sha)
    commit_base = repo.commit(base_sha)
    diff_index = commit_base.diff(commit_head)

    def pick_path(d):
        return d.b_path or d.a_path or ""

    for ctype in ('M','A','D','R'):
        for d in diff_index.iter_change_type(ctype):
            path_for_filter = pick_path(d)
            if not path_for_filter.endswith(UI_FILE_EXTENSIONS):
                continue

            raw = repo.git.diff(commit_base, commit_head, '--', (d.a_path or d.b_path))
            for patch in parse_patch(raw):
                if not getattr(patch, "changes", None):
                    continue
                oldp = getattr(getattr(patch, "header", None), "old_path", None)
                newp = getattr(getattr(patch, "header", None), "new_path", None)

                for ch in patch.changes:
                    if ch.old is None and ch.new is not None:
                        ctype_line = 'added'
                        fp = newp or path_for_filter
                        ln = ch.new
                    elif ch.new is None and ch.old is not None:
                        ctype_line = 'deleted'
                        fp = oldp or path_for_filter
                        ln = ch.old
                    else:
                        # modified 1-1 → coi phía phải là giá trị mới
                        ctype_line = 'added'
                        fp = newp or path_for_filter
                        ln = ch.new

                    for m in COMPILED_ATTRIBUTE_PATTERN.finditer(ch.line or ""):
                        if not (fp or "").endswith(UI_FILE_EXTENSIONS):
                            continue
                        changed_attributes.append({
                            'file_path': fp,
                            'line_num': ln,
                            'change_type': ctype_line,
                            'attribute_name': m.group(1),
                            'attribute_value': m.group(2)
                        })

    return changed_attributes
