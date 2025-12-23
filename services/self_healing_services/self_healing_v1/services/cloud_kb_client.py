from __future__ import annotations
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.errors
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

logger = logging.getLogger(__name__)

# Cấu hình Schema và Tên bảng
PUBLIC_KB_TABLE = "public.healing_knowledge"

def _fingerprint_hash(fp_dict):
    """Tạo mã Hash duy nhất cho một phần tử dựa trên URL và Locator."""
    if not fp_dict: 
        return ""
    
    val = str(fp_dict.get("locator_value", ""))
    normalized_val = val.replace('"', "'")
    url = str(fp_dict.get("page_url", "")).rstrip('/')
    
    clean_fp = {
        "page_url": url,
        "locator_by": fp_dict.get("locator_by", ""),
        "locator_value": normalized_val
    }
    
    fp_json = json.dumps(clean_fp, sort_keys=True)
    return hashlib.sha256(fp_json.encode()).hexdigest()

class CloudKnowledgeBaseClient:
    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self.conn = None
        self.db_config = db_config or {}
        self.enabled = False
        
        if not DB_AVAILABLE:
            logger.error("[KB Client] Thư viện psycopg2 chưa được cài đặt.")
            return

        # 1. Đồng bộ hóa cấu hình kết nối (Chuyển 'database' thành 'dbname' cho psycopg2)
        if 'database' in self.db_config:
            self.db_config['dbname'] = self.db_config.pop('database')

        if self.db_config.get('dbname'):
            try:
                # 2. Thực hiện kết nối tới PostgreSQL
                self.conn = psycopg2.connect(**self.db_config)
                self.conn.autocommit = True
                self.enabled = True
                self._ensure_schema_exists()
                logger.info(f"[KB Client] ✅ Kết nối thành công tới DB: {self.db_config['dbname']}")
            except Exception as e:
                logger.error(f"[KB Client] ❌ Kết nối thất bại: {e}")
                self.enabled = False

    def _ensure_schema_exists(self):
        """Đảm bảo cấu trúc bảng khớp với logic lưu trữ tri thức."""
        if not self.conn: 
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {PUBLIC_KB_TABLE} (
                        fingerprint_hash VARCHAR(64) PRIMARY KEY,
                        fingerprint JSONB NOT NULL,
                        project_id VARCHAR(50),
                        old_locator_by VARCHAR(20),
                        old_locator_value TEXT,
                        new_locator_by VARCHAR(20),
                        new_locator_value TEXT,
                        success_count INTEGER DEFAULT 0,
                        failure_count INTEGER DEFAULT 0,
                        success_rate FLOAT DEFAULT 0,
                        last_engine VARCHAR(50),
                        last_score FLOAT,
                        avg_repair_ms INTEGER DEFAULT 0,
                        last_success_at TIMESTAMP,
                        last_seen_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        source_type VARCHAR(20)
                    );
                """)
        except Exception as e:
            logger.warning(f"[KB Client] Schema check failed: {e}")

    def update_knowledge(self, old_locator, new_locator, fingerprint, commit_info=None, page_url=None, engine="PYTHON", score=None, duration_ms=0):
        # KHÔNG return âm thầm, phải báo lý do
        if not self.enabled:
            logger.warning("[KB Client] ⚠️ Không lưu được vì Client đang DISABLED.")
            return
        if not self.conn or self.conn.closed:
            logger.error("[KB Client] ❌ Không lưu được vì mất kết nối DB.")
            return
            
        fp_hash = _fingerprint_hash(fingerprint)
        logger.info(f"[KB Client] 🛠️ Đang chuẩn bị SQL INSERT cho hash: {fp_hash[:10]}...")

        try:
            with self.conn.cursor() as cur:
                insert_sql = f"""
                    INSERT INTO {PUBLIC_KB_TABLE} (
                        fingerprint_hash, fingerprint, 
                        old_locator_by, old_locator_value, 
                        new_locator_by, new_locator_value,
                        success_count, last_engine, last_score, 
                        avg_repair_ms, last_success_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (fingerprint_hash) 
                    DO UPDATE SET
                        success_count = {PUBLIC_KB_TABLE}.success_count + 1,
                        new_locator_by = EXCLUDED.new_locator_by,
                        new_locator_value = EXCLUDED.new_locator_value,
                        last_score = EXCLUDED.last_score,
                        updated_at = NOW();
                """
                params = (
                    fp_hash, psycopg2.extras.Json(fingerprint), 
                    old_locator[0], old_locator[1], 
                    new_locator[0], new_locator[1],
                    engine, score, duration_ms
                )
                cur.execute(insert_sql, params)
                # Đảm bảo dữ liệu được ghi xuống đĩa ngay lập tức
                self.conn.commit() 
                logger.info(f"[KB Client] ✅ THÀNH CÔNG: Tri thức đã được lưu vào Postgres.")
        except Exception as e:
            logger.error(f"[KB Client] ❌ LỖI SQL: {e}")
            
    def find_suggestion(self, fingerprint, locator_value):
        """Tìm kiếm giải pháp gợi ý từ Knowledge Base."""
        if not self.enabled or not self.conn: 
            return None
            
        fp_hash = _fingerprint_hash(fingerprint)
        query = f"SELECT * FROM {PUBLIC_KB_TABLE} WHERE fingerprint_hash = %s OR old_locator_value = %s ORDER BY success_count DESC LIMIT 1"
        
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, (fp_hash, locator_value))
                return cur.fetchone()
        except Exception as e:
            logger.error(f"[KB Client] ❌ Query Error: {e}")
            return None

    def __del__(self):
        """Đóng kết nối khi đối tượng bị hủy."""
        if self.conn and not self.conn.closed:
            try: 
                self.conn.close()
            except: 
                pass