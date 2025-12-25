import re
from thefuzz import fuzz
from collections import defaultdict
from proactive_fault_prevention.config import FUZZY_SCORER_WEIGHTS # Threshold sẽ được dùng ở bước Evaluation

def _group_changes_by_file(ui_changes):
    grouped = defaultdict(lambda: {'added': [], 'deleted': []})
    for change in ui_changes:
        if not isinstance(change, dict): 
            continue
        
        fpath = change.get('file_path')
        ctype = change.get('change_type')
        
        if fpath and ctype in ['added', 'deleted']: # Chỉ quan tâm added/deleted để tính impact
            grouped[fpath][ctype].append(change)
    return grouped

def _strategy_to_attr_name(strategy: str) -> str:
    s = (strategy or "").strip()
    s = s.replace("By.", "").replace("by.", "")
    return s.lower()

def _calculate_combined_score(old_value, new_value, attribute_name):
    # Chọn bộ trọng số dựa trên loại thuộc tính
    if attribute_name == 'class':
        weights = FUZZY_SCORER_WEIGHTS['token_set']
    else:
        weights = FUZZY_SCORER_WEIGHTS['single_string']
    
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

def is_match_strategy(git_attr_name, locator_strategy):
    git_attr = (git_attr_name or "").lower().strip()
    loc_strat = (locator_strategy or "").lower().replace(" ", "_").replace("by.", "").strip()
    
    if git_attr == loc_strat:
        return True
    
    # Hỗ trợ so khớp Text cho các Strategy phức tạp
    if git_attr == "":
        return loc_strat in ['xpath', 'css_selector', 'link_text', 'partial_link_text', 'text']
        
    return False

def predict_impact(ui_changes, locator_inventory):
    """
    F03: Xác định locator bị ảnh hưởng bằng cách ánh xạ trực tiếp từ UI Changes.
    """
    match_details = []
    impacted_locators = []
    predicted_failed_tests = set()

    if not ui_changes or not locator_inventory:
        return {"predicted_failed_tests": [], "match_details": [], "impacted_locators": []}

    # [SỬA LỖI] Lấy trực tiếp từ key của ui_changes thay vì lọc theo change_type
    all_deleted = ui_changes.get('deleted', [])
    all_added = ui_changes.get('added', [])

    seen = set()

    for locator in locator_inventory:
        # Chuẩn hóa strategy (vd: xpath, link_text)
        loc_strat = (locator.get('strategy') or "").lower().replace(" ", "_").replace("by.", "")
        loc_val = str(locator.get('value', '')).strip()

        for d_attr in all_deleted:
            g_attr = (d_attr.get('attribute_name') or "").lower()
            g_val = str(d_attr.get('attribute_value', ''))
            
            # Kiểm tra strategy có khớp để so sánh không
            if not is_match_strategy(g_attr, loc_strat):
                continue

            # Kiểm tra xem locator có chứa text bị xóa không (F03)
            is_hit = False
            if loc_strat in ['xpath', 'css_selector']:
                if g_val.lower() in loc_val.lower(): 
                    is_hit = True
            elif g_val.lower() == loc_val.lower() or fuzz.ratio(g_val.lower(), loc_val.lower()) >= 95:
                is_hit = True

            if is_hit:
                # Tìm thay đổi (Added) tốt nhất để dự đoán giá trị mới
                best_match = {'score': 0.0, 'new_val': ""}
                for a_attr in all_added:
                    # Chỉ so khớp cùng loại (ví dụ: cùng là thay đổi TEXT - attribute_name là null)
                    if (a_attr.get('attribute_name') or "").lower() == g_attr:
                        score = _calculate_combined_score(g_val, a_attr.get('attribute_value'), loc_strat)
                        if score > best_match['score']:
                            best_match['score'] = score
                            best_match['new_val'] = a_attr.get('attribute_value')

                # Nếu tìm thấy sự thay đổi tương ứng, tiến hành thay thế text trong locator
                if best_match['new_val']:
                    pattern = re.compile(re.escape(g_val), re.IGNORECASE)
                    predicted_value = pattern.sub(best_match['new_val'], loc_val)

                    # Lưu vào match_details để confidence_scorer (F06) tính điểm
                    match_details.append({"score": best_match['score']})
                    
                    # Lưu vào impacted_locators (F08)
                    key = (locator.get('test_case'), loc_val, predicted_value)
                    if key not in seen:
                        seen.add(key)
                        impacted_locators.append({
                            "test_case_id": locator.get('test_case'),
                            "step_order": locator.get('step_order'),
                            "strategy": locator.get('strategy'),
                            "value_before": loc_val,
                            "value_after": predicted_value,
                            "score": float(best_match['score'])
                        })
                        if locator.get('test_case'):
                            predicted_failed_tests.add(locator['test_case'])

    return {
        "predicted_failed_tests": list(predicted_failed_tests),
        "match_details": match_details,
        "impacted_locators": impacted_locators
    }