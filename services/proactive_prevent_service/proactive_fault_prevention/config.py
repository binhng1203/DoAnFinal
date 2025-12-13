# File: proactive_fault_prevention/config.py
import os

# =========================================
# 1. CẤU HÌNH CƠ SỞ DỮ LIỆU (DATABASE)
# =========================================
# [QUAN TRỌNG] Dùng os.getenv để Docker có thể override thành 'mongodb://mongo_db:27017/'
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "proactive_healing_db")

# =========================================
# 2. CẤU HÌNH TÍCH HỢP SYSTEM DB (POSTGRESQL) 
# =========================================
<<<<<<< Updated upstream
REPO_CACHE_DIRECTORY = "D:/FinalProject/repo_cache"     # Thư mục cache cho repo đã clone
# Mẫu regex để tìm các thuộc tính UI phổ biến
# proactive_fault_prevention/config.py

# Pattern tìm attribute có thể là locator
# Bao gồm: id, className (JSX/TSX), data-testid, aria-label, role, name, title
=======
PG_DB_HOST = os.getenv("DB_HOST", "system_db") 
PG_DB_PORT = os.getenv("DB_PORT", "5432")
PG_DB_NAME = os.getenv("DB_NAME", "final")
PG_DB_USER = os.getenv("DB_USER", "app_user")         
PG_DB_PASSWORD = os.getenv("DB_PASSWORD", "app_password") 

# Config dict để tiện ném vào psycopg2
PG_DB_CONFIG = {
    "host": PG_DB_HOST,
    "port": PG_DB_PORT,
    "dbname": PG_DB_NAME,
    "user": PG_DB_USER,
    "password": PG_DB_PASSWORD
}

# =========================================
# 3. CẤU HÌNH CHO MODULE PHÂN TÍCH (ANALYZERS)
# =========================================
# [QUAN TRỌNG] Đường dẫn cache phải là Linux path trong container (/app/...)
REPO_CACHE_DIRECTORY = os.getenv("REPO_CACHE_DIR", "/app/repo_cache")

# --- CẬP NHẬT MỚI TỪ BẠN ---
# Pattern tìm attribute có thể là locator
>>>>>>> Stashed changes
ATTRIBUTE_PATTERN = r'(id|className|data-testid|aria-label|role|name|title)="([^"]+)"'

# Danh sách các đuôi file được coi là file UI cần được phân tích
UI_FILE_EXTENSIONS = (
    ".html", ".htm", ".xml", ".jsx", ".tsx",
    ".vue", ".svelte", ".hbs", ".handlebars"
)

# Ngưỡng điểm so khớp mờ
FUZZY_MATCH_THRESHOLD = 85

# Cấu hình trọng số cho thuật toán so khớp
FUZZY_SCORER_WEIGHTS = {
    'single_string': {
        'ratio': 0.6,
        'partial_ratio': 0.3,
        'token_set_ratio': 0.1
    },
    'token_set': {
        'ratio': 0.1,
        'partial_ratio': 0.2,
        'token_set_ratio': 0.7
    }
}

# =========================================
# 4. CẤU HÌNH CHO MODULE QUÉT LOCATOR
# =========================================
# [LƯU Ý] TEST_DIRECTORIES cũ bị xóa vì Service mới quét theo file chỉ định từ API
# LOCATOR_CACHE_FILE cũng bị xóa vì không dùng cache tĩnh nữa

LOCATOR_SCANNER_TARGET_FUNCTIONS = ['find_element', 'find_elements']

# =========================================
# 5. CẤU HÌNH CHO MODULE THỰC THI TEST
# =========================================
TEST_EXECUTION_CONFIG = {
    'parallel_workers': 'auto',
    'report_file': 'test_run_report.json'
}

# =========================================
# 6. CẤU HÌNH ĐÁNH GIÁ
# =========================================
SCORE_PASS_THRESHOLD = 90
SCORE_WARN_THRESHOLD = 75