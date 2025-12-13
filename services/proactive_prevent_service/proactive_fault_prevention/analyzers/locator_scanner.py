# File: proactive_fault_prevention/analyzers/locator_scanner.py
# Chức năng: Chuyển đổi thông tin Test Steps từ DB thành Locator Inventory
# Mục đích: Chuẩn hóa dữ liệu để Impact Analyzer có thể so khớp với UI Changes.

def extract_locators_from_steps(steps_data: list):
    """
    Chuyển đổi danh sách steps lấy từ DB sang format inventory.
    
    Input steps_data (list dict): 
    [
        { "order": 1, "action": "click", "locator_type": "id", "locator_value": "btn_login", ... },
        ...
    ]
    
    Output (list dict - Inventory format):
    [
        { "strategy": "id", "value": "btn_login", "step_order": 1, "action": "click" },
        ...
    ]
    """
    inventory = []
    
    if not steps_data:
        return inventory

    for step in steps_data:
        # Lấy thông tin locator từ DB
        loc_type = step.get("locator_type")
        loc_value = step.get("locator_value")
        
        # Chỉ xử lý các step có locator hợp lệ
        if loc_type and loc_value:
            # Chuẩn hóa strategy để khớp với Impact Analyzer (thường là lowercase)
            # Ví dụ: DB lưu "ID" hoặc "By.ID" -> chuyển thành "id" hoặc giữ nguyên tùy logic analyzer
            # Ở đây ta giữ nguyên giá trị raw, Impact Analyzer sẽ tự xử lý (hàm _strategy_to_attr_name)
            
            inventory.append({
                "strategy": str(loc_type),
                "value": str(loc_value),
                # Các thông tin bổ sung để trace ngược lại
                "step_order": step.get("order"),
                "action": step.get("action"),
                # Giả lập file/test_case để Impact Analyzer không bị lỗi key
                "file": "DB_TESTCASE", 
                "test_case": f"Step_{step.get('order')}"
            })
            
    print(f"INFO: Extracted {len(inventory)} locators from DB steps.")
    return inventory