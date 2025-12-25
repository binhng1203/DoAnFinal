import pymongo
import psycopg2
import json
import hashlib
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

# Import cấu hình từ config.py
from proactive_fault_prevention.config import (
    MONGO_URI, MONGO_DB_NAME,
    PG_DB_HOST, PG_DB_PORT, PG_DB_NAME, PG_DB_USER, PG_DB_PASSWORD
)

# ======================================================
# 1. KHỞI TẠO CLIENTS
# ======================================================

# MongoDB Client
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

def get_mongo_db():
    """Trả về object Database MongoDB."""
    return mongo_client[MONGO_DB_NAME]

def get_pg_conn():
    """Tạo kết nối mới tới PostgreSQL."""
    return psycopg2.connect(
        host=PG_DB_HOST,
        port=PG_DB_PORT,
        dbname=PG_DB_NAME,
        user=PG_DB_USER,
        password=PG_DB_PASSWORD
    )

# ======================================================
# 2. THAO TÁC MONGODB (NHẬT KÝ PHÂN TÍCH - F08)
# ======================================================

def save_analysis_result(result_data):
    """Lưu toàn bộ kết quả phân tích vào MongoDB."""
    try:
        db = get_mongo_db()
        collection = db['analysis_results']
        result = collection.insert_one(result_data)
        return result.inserted_id
    except Exception as e:
        print(f"ERROR MongoDB: {e}")
        return None

def get_impact_history(project_id, limit=20):
    """Lấy lịch sử phân tích cho Dashboard."""
    try:
        db = get_mongo_db()
        cursor = db['analysis_results'].find(
            {"pr.project_id": project_id},
            {"pr": 1, "status": 1, "confidence": 1, "timestamps": 1}
        ).sort("timestamps.end", -1).limit(limit)
        
        results = list(cursor)
        for doc in results: doc["_id"] = str(doc["_id"])
        return results
    except Exception as e:
        print(f"ERROR MongoDB History: {e}")
        return []

# ======================================================
# 3. THAO TÁC POSTGRESQL (TRI THỨC HEALING - F06/F08)
# ======================================================

def upsert_proactive_healing_knowledge(loc_data, confidence_score, commit_metadata, repair_ms, source_type='PROACTIVE'):
    """
    Ghi nhận hoặc cập nhật tri thức vào PostgreSQL.
    - loc_data: Thông tin locator hỏng và locator mới.
    - source_type: 'PREDICTED' (khi mới dự báo) hoặc 'PROACTIVE' (khi đã test thành công).
    """
    # 1. Tạo fingerprint_hash (Dùng làm khóa Unique để ON CONFLICT)
    raw_id = f"{loc_data.get('project_id')}_{loc_data.get('value_before')}_{loc_data.get('strategy')}"
    fingerprint_hash = hashlib.sha256(raw_id.encode()).hexdigest()

    # 2. Tạo dummy fingerprint (Vì SQL của Xuyn để NOT NULL)
    dummy_fingerprint = json.dumps({
        "strategy": loc_data.get('strategy'),
        "value": loc_data.get('value_after'),
        "source": "proactive_system",
        "created_at": datetime.now().isoformat()
    })

    conn = None
    try:
        conn = get_pg_conn()
        cur = conn.cursor()

        # SQL Upsert Logic:
        # - Không liệt kê success_rate (Postgres tự tính).
        # - success_count chỉ tăng khi source_type là 'PROACTIVE'.
        sql = """
            INSERT INTO public.healing_knowledge (
                project_id, fingerprint, fingerprint_hash, 
                old_locator_by, old_locator_value, 
                new_locator_by, new_locator_value,
                success_count, failure_count, 
                avg_repair_ms, last_score, source_type,
                commit_info, last_success_at, updated_at, last_seen_at, last_engine
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, NOW(), NOW(), NOW(), 'PYTHON')
            ON CONFLICT (fingerprint_hash) 
            DO UPDATE SET 
                new_locator_value = EXCLUDED.new_locator_value,
                source_type = EXCLUDED.source_type,
                -- Chỉ tăng success_count nếu xác nhận thành công (PROACTIVE)
                success_count = CASE 
                    WHEN EXCLUDED.source_type = 'PROACTIVE' THEN healing_knowledge.success_count + 1 
                    ELSE healing_knowledge.success_count 
                END,
                -- Cập nhật Score và Time nếu có giá trị mới (từ bước Verify)
                last_score = CASE WHEN EXCLUDED.last_score > 0 THEN EXCLUDED.last_score ELSE healing_knowledge.last_score END,
                avg_repair_ms = CASE 
                    WHEN EXCLUDED.avg_repair_ms > 0 THEN (healing_knowledge.avg_repair_ms + EXCLUDED.avg_repair_ms) / 2
                    ELSE healing_knowledge.avg_repair_ms 
                END,
                commit_info = EXCLUDED.commit_info,
                updated_at = NOW(),
                last_seen_at = NOW();
        """

        # Trạng thái ban đầu cho bản ghi mới
        initial_success = 1 if source_type == 'PROACTIVE' else 0

        cur.execute(sql, (
            loc_data.get('project_id', 'default_project'), # 1
            dummy_fingerprint,                            # 2
            fingerprint_hash,                             # 3
            loc_data.get('strategy'),                     # 4
            loc_data.get('value_before'),                 # 5
            loc_data.get('strategy'),                     # 6
            loc_data.get('value_after'),                  # 7
            initial_success,                              # 8
            repair_ms,                                    # 9
            confidence_score,                             # 10
            source_type,                                  # 11
            json.dumps(commit_metadata)                   # 12
        ))

        conn.commit()
        cur.close()
        print(f"INFO: [Postgres] Upsert tri thức thành công ({source_type})")
        return True

    except Exception as e:
        print(f"CRITICAL ERROR PostgreSQL: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

# ======================================================
# 4. HEALTH CHECK
# ======================================================

def check_connections():
    status = {"mongo": False, "postgres": False}
    try:
        mongo_client.admin.command('ping')
        status["mongo"] = True
    except: pass
    try:
        conn = get_pg_conn()
        conn.close()
        status["postgres"] = True
    except: pass
    return status