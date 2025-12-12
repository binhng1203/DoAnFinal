# File: analyzers/impact_analyzer.py
# Chức năng: F03 & F04 - Xác định locator bị ảnh hưởng và Dự đoán test case
# Ngôn ngữ & Công nghệ: Python, TheFuzz

from thefuzz import fuzz
from collections import defaultdict
from proactive_fault_prevention.config import FUZZY_SCORER_WEIGHTS, FUZZY_MATCH_THRESHOLD

def _group_changes_by_file(ui_changes):
    grouped = defaultdict(lambda: {'added': [], 'deleted': []})
    for change in ui_changes:
        grouped[change['file_path']][change['change_type']].append(change)
    return grouped

def _strategy_to_attr_name(strategy: str) -> str:
    """
    Chuẩn hóa strategy -> tên thuộc tính UI tương ứng.
    Ví dụ: "By.ID" -> "id", "id" -> "id", "By.XPATH" -> "xpath".
    Mặc định: trả về lower-case token cuối cùng.
    """
    s = (strategy or "").strip()
    s = s.replace("By.", "").replace("by.", "")
    return s.lower()

def _calculate_combined_score(old_value, new_value, attribute_name):
    if attribute_name == 'class':
        weights = FUZZY_SCORER_WEIGHTS['token_set']
    else:  # id, name, data-testid, xpath, ...
        weights = FUZZY_SCORER_WEIGHTS['single_string']
    ratio_score = fuzz.ratio(old_value, new_value)
    partial_ratio_score = fuzz.partial_ratio(old_value, new_value)
    token_set_score = fuzz.token_set_ratio(old_value, new_value)
    weighted_score = (
        ratio_score * weights['ratio'] +
        partial_ratio_score * weights['partial_ratio'] +
        token_set_score * weights['token_set_ratio']
    )
    return float(weighted_score)

def predict_impact(ui_changes, locator_inventory):
    """
    Trả về:
    - predicted_failed_tests: list[str]
    - match_details: chi tiết match từng locator với thay đổi UI (đã khử trùng lặp)
    - impacted_locators: dạng gọn gàng cho báo cáo
    """
    predicted_failed_tests = set()
    match_details = []
    impacted_locators = []

    if not ui_changes or not locator_inventory:
        return {
            "predicted_failed_tests": [],
            "match_details": [],
            "impacted_locators": []
        }

    # Gom thay đổi theo file + tạo list toàn cục để không lệ thuộc vào tên file
    by_file = _group_changes_by_file(ui_changes)
    all_deleted = []
    all_added = []
    for f, d in by_file.items():
        all_deleted.extend(d['deleted'])
        all_added.extend(d['added'])

    # Dùng set để khử trùng lặp theo khóa đặc trưng
    seen = set()

    for locator in locator_inventory:
        loc_attr_name = _strategy_to_attr_name(locator.get('strategy', ''))
        loc_value = locator.get('value', '')

        if not loc_attr_name or not loc_value:
            continue

        # 1) Tìm những thay đổi 'deleted' có attribute_value == locator.value
        #    và attribute_name khớp với strategy (vd: id ↔ By.ID)
        deleted_candidates = [
            d for d in all_deleted
            if d.get('attribute_value') == loc_value
            and d.get('attribute_name', '').lower() == loc_attr_name
        ]
        if not deleted_candidates:
            # Nếu không thấy xóa đúng value, có thể locator bị đổi kiểu/format;
            # Vẫn thử partial match nhẹ (an toàn): ưu tiên exact trước, fallback partial.
            deleted_candidates = [
                d for d in all_deleted
                if d.get('attribute_name', '').lower() == loc_attr_name
                and fuzz.partial_ratio(loc_value, d.get('attribute_value', '')) >= 95
            ]
        if not deleted_candidates:
            continue

        # 2) Với mỗi 'deleted', tìm 'added' tốt nhất có cùng attribute_name
        #    Ưu tiên cùng file, nếu không có thì xét all_added.
        for deleted_attr in deleted_candidates:
            file_scope_added = [
                a for a in by_file.get(deleted_attr['file_path'], {}).get('added', [])
                if a.get('attribute_name', '').lower() == loc_attr_name
            ]
            candidates_added = file_scope_added if file_scope_added else [
                a for a in all_added
                if a.get('attribute_name', '').lower() == loc_attr_name
            ]
            if not candidates_added:
                continue

            best = {'score': 0.0, 'attribute': None}
            for added_attr in candidates_added:
                score = _calculate_combined_score(
                    deleted_attr.get('attribute_value', ''),
                    added_attr.get('attribute_value', ''),
                    loc_attr_name
                )
                if score > best['score']:
                    best['score'] = score
                    best['attribute'] = added_attr

            if not best['attribute'] or best['score'] < FUZZY_MATCH_THRESHOLD:
                continue

            md = {
                'locator': locator,
                'deleted_attribute': deleted_attr,
                'predicted_attribute': best['attribute'],
                'score': best['score']
            }

            # Khóa khử trùng lặp
            key = (
                locator.get('file'),
                locator.get('test_case'),
                loc_attr_name,
                deleted_attr.get('attribute_value'),
                best['attribute'].get('attribute_value'),
                deleted_attr.get('file_path')
            )
            if key in seen:
                continue
            seen.add(key)
            match_details.append(md)

            impacted_locators.append({
                "test_file": locator.get('file'),
                "test_case": locator.get('test_case'),
                "strategy": locator.get('strategy'),
                "value_before": deleted_attr.get('attribute_value'),
                "value_after": best['attribute'].get('attribute_value'),
                "ui_file": deleted_attr.get('file_path'),
                "line_deleted": deleted_attr.get('line_num'),
                "line_added": best['attribute'].get('line_num'),
                "score": best['score']
            })

            if locator.get('test_case'):
                predicted_failed_tests.add(f"{locator['file']}::{locator['test_case']}")

    return {
        "predicted_failed_tests": list(predicted_failed_tests),
        "match_details": match_details,
        "impacted_locators": impacted_locators
    }
