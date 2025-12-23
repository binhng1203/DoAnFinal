# File: persistence/database_handler.py
import pymongo
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from proactive_fault_prevention.config import MONGO_URI, MONGO_DB_NAME
import time

# ======================================================
# KHỞI TẠO CLIENT (Lazy Connection)
# ======================================================
# PyMongo là thread-safe và có connection pooling. 
# Ta chỉ khởi tạo object, chưa cần kết nối ngay lập tức.
# serverSelectionTimeoutMS: Thời gian chờ tối đa trước khi báo lỗi kết nối.
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

def get_db():
    """
    Trả về object Database. 
    PyMongo sẽ tự động kết nối khi có lệnh query thực sự được gọi.
    """
    return client[MONGO_DB_NAME]

def check_connection():
    """
    Hàm tiện ích để kiểm tra kết nối (Dùng cho Health Check API nếu cần)
    """
    try:
        # Lệnh ping nhẹ nhất
        client.admin.command('ping')
        return True
    except Exception as e:
        print(f"WARNING: MongoDB connection check failed: {e}")
        return False

# ======================================================
# CÁC HÀM THAO TÁC DỮ LIỆU
# ======================================================

def save_analysis_result(result_data):
    """
    Lưu kết quả phân tích.
    """
    try:
        db = get_db()
        # [QUAN TRỌNG] Thống nhất tên collection là 'analysis_results'
        collection = db['analysis_results']
        
        result = collection.insert_one(result_data)
        
        # Log ra ID dạng string để dễ debug
        print(f"SUCCESS: Saved analysis result to DB. ID: {result.inserted_id}")
        return result.inserted_id

    except ServerSelectionTimeoutError:
        print("ERROR: Could not connect to MongoDB (Timeout). Check if Mongo container is running.")
        return None
    except Exception as e:
        print(f"ERROR: Failed to save analysis result: {e}")
        return None

def save_healing_log(log_data):
    """
    Lưu bản ghi self-healing.
    """
    try:
        db = get_db()
        collection = db['healing']
        result = collection.insert_one(log_data)
        print(f"SUCCESS: Saved healing log. ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        print(f"ERROR: Failed to save healing log: {e}")
        return None

def get_analysis_by_commit(commit_sha):
    """
    Truy vấn kết quả phân tích theo commit SHA.
    """
    try:
        db = get_db()
        # [FIX] Đã sửa tên collection khớp với hàm save ('analysis_results')
        collection = db['analysis_results'] 
        
        # Tìm bản ghi mới nhất của commit đó
        return collection.find_one(
            {'pr.head_sha': commit_sha},  # Lưu ý: Cấu trúc data của bạn SHA nằm trong object 'pr'
            sort=[('_id', -1)]
        )
    except Exception as e:
        print(f"ERROR: Fetching analysis by commit: {e}")
        return None