# File: config.py

# =========================================
# CẤU HÌNH CƠ SỞ DỮ LIỆU (DATABASE)
# =========================================
MONGO_URI = "mongodb://localhost:27017/"    # URI kết nối đến server MongoDB 
MONGO_DB_NAME = "proactive_healing_db"

# =========================================
# CẤU HÌNH CHO MODULE PHÂN TÍCH (ANALYZERS)
# =========================================
REPO_CACHE_DIRECTORY = "D:/FinalProject/repo_cache"     # Thư mục cache cho repo đã clone
# Mẫu regex để tìm các thuộc tính UI phổ biến
ATTRIBUTE_PATTERN = r'\b(id|class|name|data-testid)\s*=\s*["\'](.*?)["\']'
# Danh sách các đuôi file được coi là file UI cần được phân tích
UI_FILE_EXTENSIONS = ('.html', '.jsx', '.vue', '.tsx', '.css', '.scss')
# Ngưỡng điểm so khớp mờ để coi là một dự đoán hợp lệ
FUZZY_MATCH_THRESHOLD = 85
# Cấu hình trọng số cho các thuật toán so khớp mờ
FUZZY_SCORER_WEIGHTS = {
    # Trọng số cho các thuộc tính dạng chuỗi đơn (id, name, data-testid)
    'single_string': {
        'ratio': 0.6,          # Ưu tiên cao cho lỗi chính tả
        'partial_ratio': 0.3,  # Tốt cho việc thêm/bớt tiền tố/hậu tố
        'token_set_ratio': 0.1 # Trọng số thấp vì ít có token
    },
    # Trọng số cho thuộc tính 'class' (dạng tập hợp token)
    'token_set': {
        'ratio': 0.1,          # Trọng số thấp vì thứ tự không quan trọng
        'partial_ratio': 0.2,
        'token_set_ratio': 0.7 # Ưu tiên cao nhất vì nó bỏ qua thứ tự và trùng lặp
    }
}

# =========================================
# CẤU HÌNH CHO MODULE QUÉT LOCATOR
# =========================================
# Các thư mục chứa mã nguồn kiểm thử cần được quét
TEST_DIRECTORIES = [r"D:\FinalProject\sample_project\tests"]
# Tên các hàm mà máy quét sẽ tìm kiếm. Dễ dàng mở rộng cho các hàm tùy chỉnh.
LOCATOR_SCANNER_TARGET_FUNCTIONS = ['find_element', 'find_elements']
# Đường dẫn đến tệp cache cho kho locator
LOCATOR_CACHE_FILE = 'locator_cache.json'

# =========================================
# CẤU HÌNH CHO MODULE THỰC THI TEST (EXECUTION)
# =========================================
TEST_EXECUTION_CONFIG = {
    # Số luồng chạy song song. 'auto' sẽ sử dụng số nhân CPU.
    'parallel_workers': 'auto',
    # Tên tệp để lưu báo cáo kết quả dạng JSON
    'report_file': 'test_run_report.json'
}

# =========================================
# CẤU HÌNH CHO MODULE ĐÁNH GIÁ (EVALUATION)
# =========================================
# Ngưỡng điểm tổng hợp để phân loại là PASS
SCORE_PASS_THRESHOLD = 90
# Ngưỡng điểm tổng hợp để phân loại là WARN
SCORE_WARN_THRESHOLD = 75


