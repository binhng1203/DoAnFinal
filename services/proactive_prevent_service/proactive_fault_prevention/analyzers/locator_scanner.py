# File: proactive_fault_prevention/analyzers/locator_scanner.py
# Chức năng: Chuyển đổi thông tin Test Steps từ DB thành Locator Inventory
# Mục đích: Chuẩn hóa dữ liệu để Impact Analyzer có thể so khớp với UI Changes.

def extract_locators_from_steps(steps_data: list, test_case_identifier=None):
    """
    Chuyển đổi danh sách steps từ DB sang format inventory chuẩn.
    
    Args:
        steps_data: Dữ liệu các bước lấy từ database.
        test_case_identifier: Tên test case dùng để gán nhãn cho kết quả phân tích.
    """
    inventory = []
    
    if not steps_data:
        return inventory

    for step in steps_data:
        loc_type = step.get("locator_type")
        loc_value = step.get("locator_value")
        
        if loc_type and loc_value:
            # Gán tên test case thực tế lấy từ Data Fetcher
            case_name = test_case_identifier or "Unknown_TestCase"
            
            inventory.append({
                "strategy": str(loc_type),
                "value": str(loc_value),
                "step_order": step.get("order"),
                "action": step.get("action"),
                "file": "DATABASE", 
                "test_case": case_name  # Khắc phục lỗi định danh bị thiếu
            })
            
    print(f"INFO: Extracted {len(inventory)} locators for case: {test_case_identifier}")
    return inventory