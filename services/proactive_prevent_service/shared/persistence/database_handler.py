# File: persistence/database_handler.py
# Chức năng: F08 - Lưu trữ dữ liệu

import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, WriteError
from proactive_fault_prevention.config import MONGO_URI, MONGO_DB_NAME

# Khởi tạo client dùng chung
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # Kiểm tra kết nối ngay khi khởi động
    client.admin.command('hello')
    print(f"Successfully connected to MongoDB server. Using database: '{MONGO_DB_NAME}'")
except ConnectionFailure as e:
    print(f"FATAL: Could not connect to MongoDB: {e}")
    client = None

def get_db():
    """
    Thiết lập kết nối đến MongoDB và trả về database object.
    """
    if not client:
        # Cho phép hàm gọi bắt lỗi và xử lý
        raise Exception("MongoDB client is not connected. Cannot perform database operations.")
    return client[MONGO_DB_NAME]

def save_analysis_result(result_data):
    try:
        db = get_db()
        collection = db['analysis_results']
        result = collection.insert_one(result_data)
        print(f"Successfully saved analysis result to the database with ID: {result.inserted_id}")
        return result.inserted_id
    except WriteError as e:
        print(f"Error writing analysis result to MongoDB: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during save_analysis_result: {e}")
        return None

def save_healing_log(log_data):
    """
    Lưu bản ghi self-healing vào collection 'healing'.
    """
    try:
        db = get_db()
        collection = db['healing']
        result = collection.insert_one(log_data)
        print(f"Successfully saved healing log with ID: {result.inserted_id}")
        return result.inserted_id
    except WriteError as e:
        print(f"Error writing healing log to MongoDB: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during save_healing_log: {e}")
        return None

def get_analysis_by_commit(commit_sha):
    """
    Truy vấn một kết quả phân tích dựa trên commit SHA.
    """
    try:
        db = get_db()
        collection = db['proactive']
        return collection.find_one({'commit_sha': commit_sha})
    except Exception as e:
        print(f"Error fetching analysis by commit: {e}")
        return None

# Gợi ý index (chạy 1 lần trong MongoDB nếu cần hiệu năng cao):
# db.proactive.createIndex({ "commit_sha": 1 }, { unique: true })
# db.proactive.createIndex({ "pull_request_number": 1 })
# db.proactive.createIndex({ "timestamp": -1 })
# db.healing.createIndex({ "test_case_identifier": 1 })
# db.healing.createIndex({ "timestamp": -1 })
