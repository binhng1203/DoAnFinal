# File: proactive_fault_prevention/analyzers/impact_analyzer.py
from thefuzz import fuzz
from collections import defaultdict
from proactive_fault_prevention.config import FUZZY_SCORER_WEIGHTS, FUZZY_MATCH_THRESHOLD

def _group_changes_by_file(ui_changes):
    grouped = defaultdict(lambda: {'added': [], 'deleted': []})
    for change in ui_changes:
        # Kiểm tra an toàn để tránh lỗi dữ liệu rác
        if not isinstance(change, dict): 
            continue
        
        fpath = change.get('file_path')
        ctype = change.get('change_type')
        
        if fpath and ctype in grouped[fpath]:
            grouped[fpath][ctype].append(change)
    return grouped

def _strategy_to_attr_name(strategy: str) -> str:
    s = (strategy or "").strip()
    s = s.replace("By.", "").replace("by.", "")
    return s.lower()

def _calculate_combined_score(old_value, new_value, attribute_name):
    # (Giữ nguyên logic cũ)
    if attribute_name == 'class':
        weights = FUZZY_SCORER_WEIGHTS['token_set']
    else:
        weights = FUZZY_SCORER_WEIGHTS['single_string']
    
    # Ép kiểu string để tránh lỗi nếu value là None/Int
    old_str = str(old_value or "")
    new_str = str(new_value or "")

    ratio_score = fuzz.ratio(old_str, new_str)
    partial_ratio_score = fuzz.partial_ratio(old_str, new_str)
    token_set_score = fuzz.token_set_ratio(old_str, new_str)
    
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
    - match_details: chi tiết match từng locator với thay đổi UI
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

    # ========================================================
    # [FIX] NORMALIZE INPUT: Xử lý trường hợp input là Dict
    # ========================================================
    normalized_changes = []
    if isinstance(ui_changes, dict):
        # Nếu là dict {added: [], deleted: []}, gom tất cả vào 1 list phẳng
        for key, changes in ui_changes.items():
            if isinstance(changes, list):
                normalized_changes.extend(changes)
    elif isinstance(ui_changes, list):
        normalized_changes = ui_changes
    else:
        print(f"WARNING: Unknown format for ui_changes: {type(ui_changes)}")
        return {"predicted_failed_tests": [], "match_details": [], "impacted_locators": []}

    # Gom thay đổi theo file
    by_file = _group_changes_by_file(normalized_changes)
    
    all_deleted = []
    all_added = []
    for f, d in by_file.items():
        all_deleted.extend(d['deleted'])
        all_added.extend(d['added'])

    seen = set()

    # Duyệt qua kho locator (lấy từ DB steps hoặc scan file)
    for locator in locator_inventory:
        # Locator từ DB steps sẽ có field 'strategy' (vd: 'id', 'xpath')
        loc_attr_name = _strategy_to_attr_name(locator.get('strategy', ''))
        loc_value = locator.get('value', '')

        if not loc_attr_name or not loc_value:
            continue

        # 1) Tìm thay đổi 'deleted' khớp chính xác value & name
        deleted_candidates = [
            d for d in all_deleted
            if str(d.get('attribute_value')) == str(loc_value)
            and d.get('attribute_name', '').lower() == loc_attr_name
        ]
        
        # Fallback: Nếu không khớp chính xác, thử partial match (phòng trường hợp format thay đổi nhẹ)
        if not deleted_candidates:
            deleted_candidates = [
                d for d in all_deleted
                if d.get('attribute_name', '').lower() == loc_attr_name
                and fuzz.partial_ratio(str(loc_value), str(d.get('attribute_value', ''))) >= 95
            ]
            
        if not deleted_candidates:
            continue

        # 2) Với mỗi 'deleted', tìm 'added' tốt nhất
        for deleted_attr in deleted_candidates:
            # Ưu tiên tìm 'added' trong CÙNG FILE UI
            file_scope_added = [
                a for a in by_file.get(deleted_attr['file_path'], {}).get('added', [])
                if a.get('attribute_name', '').lower() == loc_attr_name
            ]
            # Nếu không có, tìm trong toàn bộ 'added'
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

            # Tìm thấy Match! Lưu kết quả
            md = {
                'locator': locator,
                'deleted_attribute': deleted_attr,
                'predicted_attribute': best['attribute'],
                'score': best['score']
            }

            # Khóa khử trùng lặp
            key = (
                locator.get('file', 'DB'),
                locator.get('test_case', 'Unknown'),
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
                "test_case_id": locator.get('test_case'), # ID hoặc tên step
                "step_order": locator.get('step_order'),
                "strategy": locator.get('strategy'),
                "value_before": deleted_attr.get('attribute_value'),
                "value_after": best['attribute'].get('attribute_value'),
                "ui_file": deleted_attr.get('file_path'),
                "line_deleted": deleted_attr.get('line_num'),
                "line_added": best['attribute'].get('line_num'),
                "score": best['score']
            })

            # Nếu có tên test case (để chạy lại)
            if locator.get('test_case'):
                predicted_failed_tests.add(locator['test_case'])

    return {
        "predicted_failed_tests": list(predicted_failed_tests),
        "match_details": match_details,
        "impacted_locators": impacted_locators
    }