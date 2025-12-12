# File: analyzers/locator_scanner.py
# Chức năng: F03 - Xác định locator bị ảnh hưởng (phần quét mã nguồn)
# Ngôn ngữ & Công nghệ: Python, ast
# Mục đích: Phân tích tĩnh mã nguồn Python của các kịch bản test để
# xây dựng một kho (inventory) chứa tất cả các locator Selenium đang được sử dụng.

import ast
import os
import json
import hashlib
from pathlib import Path
from proactive_fault_prevention.config import TEST_DIRECTORIES, LOCATOR_SCANNER_TARGET_FUNCTIONS, LOCATOR_CACHE_FILE


def _normalize_path(p: str) -> str:
    """Chuẩn hoá đường dẫn để so sánh/hiển thị ổn định (Windows/Linux)."""
    try:
        # Không dùng strict để không vỡ khi file mới/đã xoá
        p_obj = Path(p).resolve(strict=False)
        p_str = str(p_obj)
    except Exception:
        p_str = p
    # normpath + normcase rồi chuyển '\' -> '/'
    return os.path.normcase(os.path.normpath(p_str)).replace("\\", "/")


class LocatorVisitor(ast.NodeVisitor):
    """
    Duyệt AST để tìm các lệnh gọi hàm tìm kiếm locator (find_element/find_elements).
    """
    def __init__(self, filepath, target_functions):
        self.filepath_raw = filepath
        self.filepath = _normalize_path(filepath)
        self.target_functions = set(target_functions)
        self.locators = []
        self.current_test_case = None

    def visit_FunctionDef(self, node):
        # Lưu ngữ cảnh test case hiện tại (an toàn cho hàm lồng nhau)
        prev_case = self.current_test_case
        if node.name.startswith('test_'):
            self.current_test_case = node.name
        self.generic_visit(node)
        self.current_test_case = prev_case

    def _extract_string_like(self, node):
        """Lấy giá trị chuỗi từ AST node (Constant/Str/JoinedStr best-effort)."""
        if isinstance(node, ast.Constant):
            return node.value
        if hasattr(ast, "Str") and isinstance(node, ast.Str):
            return node.s
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value))
                elif hasattr(ast, "Str") and isinstance(v, ast.Str):
                    parts.append(v.s)
                else:
                    parts.append("{expr}")
            return "".join(parts)
        return None

    def _extract_strategy(self, node):
        """
        Lấy strategy (by) từ đối số:
        - By.ID  -> "By.ID"
        - "id"   -> "id"
        - name token -> tên biến (best-effort)
        """
        # By.ID
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "By":
            return f"By.{node.attr}"
        # "id" / "xpath" ...
        s = self._extract_string_like(node)
        if s is not None:
            return str(s)
        # Tên biến (ít gặp)
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _extract_positional_args(self, node):
        """Trả về (strategy, value) khi dùng positional args."""
        if len(node.args) >= 2:
            strategy = self._extract_strategy(node.args[0])
            value = self._extract_string_like(node.args[1])
            return strategy, value
        return None, None

    def _extract_keyword_args(self, node):
        """Trả về (strategy, value) khi dùng keyword args (by=..., value=...)."""
        by_node = None
        val_node = None
        for kw in getattr(node, "keywords", []) or []:
            if kw.arg == "by":
                by_node = kw.value
            elif kw.arg in ("value", "selector"):  # tuỳ driver wrapper
                val_node = kw.value
        strategy = self._extract_strategy(by_node) if by_node is not None else None
        value = self._extract_string_like(val_node) if val_node is not None else None
        return strategy, value

    def visit_Call(self, node):
        # Tìm các call dạng x.find_element(...), x.find_elements(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr in self.target_functions:
            strategy, value = None, None

            # Ưu tiên positional nếu đủ 2 tham số
            ps, pv = self._extract_positional_args(node)
            if ps is not None and pv is not None:
                strategy, value = ps, pv
            else:
                # Thử keyword args
                ks, kv = self._extract_keyword_args(node)
                if ks is not None and kv is not None:
                    strategy, value = ks, kv

            if strategy is not None and value is not None:
                self.locators.append({
                    "file": self.filepath,                 # đã chuẩn hoá
                    "test_case": self.current_test_case,   # có thể None nếu ngoài test_*
                    "strategy": strategy,
                    "value": value,
                    "line": node.lineno
                })

        self.generic_visit(node)


def _calculate_file_hash(filepath):
    """Tính toán hash SHA256 của một tệp."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        hasher.update(f.read())
    return hasher.hexdigest()


def _iter_test_files(test_paths):
    """
    Nhận cả thư mục lẫn file .py đơn lẻ trong TEST_DIRECTORIES.
    """
    for path in test_paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith('.py'):
                        yield os.path.join(root, file)
        elif os.path.isfile(path) and path.endswith('.py'):
            yield path
        else:
            print(f"WARNING: Test path not found or unsupported: {path}")


def scan_for_locators():
    """
    Quét source test để xây dựng kho locator có cache.
    """
    # --- load cache an toàn ---
    cache_data = {'hashes': {}, 'inventory': []}
    if os.path.exists(LOCATOR_CACHE_FILE):
        try:
            with open(LOCATOR_CACHE_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    cache_data['hashes'] = loaded.get('hashes', {})
                    cache_data['inventory'] = loaded.get('inventory', [])
        except (json.JSONDecodeError, OSError):
            print("WARNING: Cache file is corrupted. Rebuilding.")

    # Chuẩn hoá inventory cũ (phòng khi bản cũ lưu path kiểu khác)
    inventory = []
    for loc in cache_data.get('inventory', []):
        loc = dict(loc)
        if 'file' in loc:
            loc['file'] = _normalize_path(loc['file'])
        inventory.append(loc)

    cached_hashes = dict(cache_data.get('hashes', {}))
    # CŨNG chuẩn hoá key của cached_hashes để tránh trùng key do slash khác
    cached_hashes = { _normalize_path(k): v for k, v in cached_hashes.items() }

    current_hashes = {}
    files_to_scan = []

    # --- xác định file cần scan ---
    for fp in _iter_test_files(TEST_DIRECTORIES):
        fp_norm = _normalize_path(fp)
        try:
            file_hash = _calculate_file_hash(fp)
        except OSError as e:
            print(f"WARNING: Could not read {fp}: {e}")
            continue
        current_hashes[fp_norm] = file_hash
        if cached_hashes.get(fp_norm) != file_hash:
            files_to_scan.append(fp)

    if not files_to_scan and inventory:
        print("INFO: Locator inventory is up to date. Loading from cache.")
        return inventory

    print(f"INFO: Scanning {len(files_to_scan)} new/modified test file(s)...")
    newly_found_locators = []

    for filepath in files_to_scan:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
            tree = ast.parse(source_code, filename=filepath)
            visitor = LocatorVisitor(filepath, LOCATOR_SCANNER_TARGET_FUNCTIONS)
            visitor.visit(tree)
            newly_found_locators.extend(visitor.locators)
        except SyntaxError as e:
            print(f"WARNING: Could not parse {filepath} due to syntax error: {e}")
        except OSError as e:
            print(f"WARNING: Could not read {filepath}: {e}")

    # Loại bỏ các locator thuộc file đã thay đổi khỏi inventory cũ, rồi cộng cái mới
    changed_files = { _normalize_path(p) for p in files_to_scan }
    updated_inventory = [loc for loc in inventory if _normalize_path(loc.get('file', '')) not in changed_files]
    updated_inventory.extend(newly_found_locators)

    # --- ghi cache ---
    try:
        with open(LOCATOR_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    'hashes': current_hashes,      # key đã là path chuẩn hoá
                    'inventory': updated_inventory
                },
                f, indent=2, ensure_ascii=False
            )
        print("INFO: Locator inventory scan complete and cache updated.")
    except OSError as e:
        print(f"WARNING: Could not write cache file {LOCATOR_CACHE_FILE}: {e}")

    return updated_inventory
