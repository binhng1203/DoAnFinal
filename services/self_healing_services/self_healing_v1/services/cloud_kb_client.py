from __future__ import annotations

import json
import hashlib
from datetime import datetime
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

PUBLIC_KB_TABLE = "public.healing_knowledge"
MANUAL_OVERRIDE_TABLE = "custom_analytics.manual_override_mapping"
PROJECT_TABLE = "custom_analytics.project"


def _fingerprint_hash(fp_dict):
    if not fp_dict: return ""
    
    # CHUẨN HÓA: Chuyển tất cả nháy kép thành nháy đơn trước khi Hash
    val = str(fp_dict.get("locator_value", ""))
    normalized_val = val.replace('"', "'")
    
    # Loại bỏ dấu xuyệt cuối URL
    url = str(fp_dict.get("page_url", "")).rstrip('/')
    
    clean_fp = {
        "page_url": url,
        "locator_by": fp_dict.get("locator_by", ""),
        "locator_value": normalized_val
    }
    
    # Sắp xếp key để đảm bảo chuỗi JSON luôn duy nhất
    fp_json = json.dumps(clean_fp, sort_keys=True)
    return hashlib.sha256(fp_json.encode()).hexdigest()

class CloudKnowledgeBaseClient:

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self.conn = None
        self.db_config = db_config or {}
        self.enabled = False

        if not DB_AVAILABLE:
            logger.warning("[KB Client] psycopg2 chưa cài đặt.")
            return

        # --- LOGIC LINH HOẠT Ở ĐÂY ---
        # Thử lấy 'dbname', nếu không có thì thử lấy 'database'
        actual_db_name = self.db_config.get('dbname') or self.db_config.get('database')
        
        if self.db_config and actual_db_name:
            # Chuẩn hóa lại cho psycopg2 (thư viện này bắt buộc dùng key 'dbname')
            if 'database' in self.db_config:
                self.db_config['dbname'] = self.db_config.pop('database')
            
            self.enabled = True
            try:
                self.conn = psycopg2.connect(**self.db_config)
                psycopg2.extras.register_json(self.conn)
                self.conn.autocommit = True
                logger.info(f"[KB Client] ✅ Kết nối thành công tới DB: {actual_db_name}")
            except Exception as e:
                logger.error(f"[KB Client] ❌ Kết nối thất bại: {e}")
                self.enabled = False
        else:
            logger.info("[KB Client] ⚠️ Thiếu config (dbname/database). Chế độ Offline.")
    def _ensure_schema_exists(self):
        """Đảm bảo bảng healing_knowledge tồn tại để không bị lỗi khi ghi."""
        if not self.conn: return
        try:
            with self.conn.cursor() as cur:
                # Kiểm tra và tạo bảng nếu chưa có (Dựa trên schema bạn đang dùng)
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {PUBLIC_KB_TABLE} (
                        fingerprint_hash VARCHAR(64) PRIMARY KEY,
                        fingerprint_json JSONB,
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
                        updated_at TIMESTAMP DEFAULT NOW(),
                        source_type VARCHAR(20)
                    );
                """)
                logger.debug(f"[KB Client] Schema check: Table {PUBLIC_KB_TABLE} is ready.")
        except Exception as e:
            logger.warning(f"[KB Client] Không thể kiểm tra/tạo schema: {e}")
    # ---------------------------------------------------------
    # Helper: resolve project_id
    # ---------------------------------------------------------
    def _resolve_project_id(self, cur, page_url: Optional[str] = None) -> Optional[str]:
        """
        Lấy project_id từ DB hoặc tạo hash từ URL.
        """
        try:
            if not page_url:
                return None

            # 1) Kiểm tra bảng project
            try:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'custom_analytics' AND table_name = 'project'
                    );
                    """
                )
                exists = cur.fetchone()
                if exists and exists[0]:
                    from urllib.parse import urlparse
                    host = urlparse(page_url).netloc
                    
                    if host:
                        # Match theo base_url
                        cur.execute(
                            """
                            SELECT project_id FROM custom_analytics.project
                            WHERE base_url IS NOT NULL AND %s ILIKE CONCAT('%%', base_url, '%%')
                            LIMIT 1;
                            """, (host,)
                        )
                        row = cur.fetchone()
                        if row: return str(row[0])
                    
                    # Match theo url_patterns array
                    cur.execute(
                        """
                        SELECT project_id FROM custom_analytics.project
                        WHERE url_patterns IS NOT NULL AND %s = ANY(url_patterns)
                        LIMIT 1;
                        """, (page_url,)
                    )
                    row2 = cur.fetchone()
                    if row2: return str(row2[0])
            except Exception:
                pass # Bỏ qua lỗi schema check

            # 2) Fallback: deterministic id từ host/url
            hash_input = page_url
            try:
                from urllib.parse import urlparse
                parsed = urlparse(page_url)
                hash_input = parsed.netloc or page_url
            except Exception:
                pass
            
            h = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
            return h[:8]

        except Exception as e:
            logger.debug(f"[KB Client] _resolve_project_id failed: {e}")
            return None
        
    def query_suggestion(self, fingerprint: Dict[str, Any], locator_value: str) -> Optional[Dict[str, Any]]:
        suggestions = self.get_suggestions(fingerprint, page_url=fingerprint.get("page_url"))
        if suggestions:
            best = suggestions[0]
            return {
                "new_locator_by": best.get("by"),
                "new_locator_value": best.get("value"),
                "success_rate": best.get("success_rate", 0.0),
                "score": best.get("score", 0.0)
            }
        return None
    # ---------------------------------------------------------
    # Core Functions
    # ---------------------------------------------------------
    def find_suggestion(self, fingerprint, locator_value):
        """
        [CLIENT] Thực thi SQL để tìm tri thức từ Postgres.
        """
        # 1. Nếu Client chưa kết nối thành công thì bỏ qua
        if not self.enabled or not self.conn:
            return None

        # 2. Tạo mã Hash để đối chiếu
        fp_hash = _fingerprint_hash(fingerprint)
        
        # 3. SQL: Bỏ project_id, ưu tiên Hash, sau đó đến Locator gốc
        query = f"""
            SELECT * FROM {PUBLIC_KB_TABLE} 
            WHERE fingerprint_hash = %s 
               OR old_locator_value = %s
            ORDER BY success_rate DESC, last_success_at DESC 
            LIMIT 1
        """
        
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, (fp_hash, locator_value))
                result = cur.fetchone()
                if result:
                    logger.info(f"[KB Client] 🎯 Match found in DB (Hash: {result['fingerprint_hash'][:8]})")
                return result
        except Exception as e:
            logger.error(f"[KB Client] Find suggestion SQL failed: {e}")
            return None
        
    def get_suggestions(
        self,
        fingerprint: Dict[str, Any],
        page_url: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        
        # [QUAN TRỌNG] Nếu client bị disable, trả về rỗng ngay lập tức
        if not self.enabled:
            return []

        fp_hash = _fingerprint_hash(fingerprint)
        suggestions: List[Dict[str, Any]] = []
        temp_conn = None

        try:
            # Tạo kết nối tạm thời để đảm bảo thread-safety hoặc dùng lại kết nối chính
            # Ở đây tạo mới để an toàn cho autocommit
            temp_conn = psycopg2.connect(**self.db_config)
            psycopg2.extras.register_json(temp_conn)
            temp_conn.autocommit = True

            with temp_conn.cursor() as cur:
                # Set schema path để query gọn hơn
                try:
                    cur.execute("SET search_path TO custom_analytics, public;")
                except Exception:
                    pass

                project_id = self._resolve_project_id(cur, page_url)

                # --- 1. Manual Override Check ---
                try:
                    # Check table exists first
                    cur.execute(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='custom_analytics' AND table_name=%s)",
                        (MANUAL_OVERRIDE_TABLE.split('.')[-1],)
                    )
                    if cur.fetchone()[0] and project_id:
                        cur.execute(
                            f"""
                            SELECT locator_new FROM {MANUAL_OVERRIDE_TABLE}
                            WHERE project_id=%s AND fingerprint_hash=%s AND is_active=TRUE
                            ORDER BY updated_at DESC LIMIT %s
                            """,
                            (project_id, fp_hash, limit)
                        )
                        rows = cur.fetchall()
                        for (loc_new,) in rows:
                            try:
                                by_new, val_new = loc_new.split("=", 1)
                                suggestions.append({
                                    "by": by_new.strip(), "value": val_new.strip(), 
                                    "score": 1.0, "source": "manual_override"
                                })
                            except: continue
                        
                        if suggestions:
                            logger.info(f"[Suggestion] Found {len(suggestions)} manual overrides.")
                            return suggestions
                except Exception:
                    pass # Ignore manual override errors

                # --- 2. Query KB (Variant A: Schema chuẩn với fingerprint_hash) ---
                try:
                    query = f"""
                        SELECT new_locator_by, new_locator_value, success_rate, success_count, last_engine, last_score
                        FROM {PUBLIC_KB_TABLE}
                        WHERE fingerprint_hash=%s 
                        {'AND project_id=%s' if project_id else ''}
                        ORDER BY success_rate DESC, success_count DESC, last_seen_at DESC
                        LIMIT %s
                    """
                    params = (fp_hash, project_id, limit) if project_id else (fp_hash, limit)
                    cur.execute(query, params)
                    
                    rows = cur.fetchall()
                    for r in rows:
                        new_by, new_val, s_rate, s_count, engine, l_score = r
                        # Tính score
                        final_score = float(l_score) if l_score is not None else 0.0
                        if s_rate is not None:
                            final_score = max(final_score, float(s_rate) / 100.0)
                        
                        suggestions.append({
                            "by": new_by, "value": new_val, "score": final_score,
                            "source": f"kb_{str(engine).lower() if engine else 'auto'}",
                            "success_rate": float(s_rate) if s_rate else 0.0
                        })
                    
                    if suggestions:
                        logger.info(f"[Suggestion] Found {len(suggestions)} candidates from KB (Variant A).")
                        return suggestions

                except psycopg2.errors.UndefinedColumn:
                    # Fallback sang Variant B nếu cột không khớp
                    pass 
                except Exception as e:
                    logger.debug(f"[Suggestion] KB Query Variant A Error: {e}")

                # --- 3. Query KB (Variant B: Schema cũ dùng JSONB) ---
                if not suggestions:
                    try:
                        fp_json = psycopg2.extras.Json(fingerprint or {})
                        query = f"""
                            SELECT new_locator_by, new_locator_value, success_count, failure_count, source_type
                            FROM {PUBLIC_KB_TABLE}
                            WHERE fingerprint=%s
                            {'AND project_id=%s' if project_id else ''}
                            ORDER BY success_count DESC, last_success_at DESC
                            LIMIT %s
                        """
                        params = (fp_json, project_id, limit) if project_id else (fp_json, limit)
                        cur.execute(query, params)
                        
                        rows = cur.fetchall()
                        for r in rows:
                            new_by, new_val, s_count, f_count, src_type = r
                            total = (s_count or 0) + (f_count or 0)
                            rate = (s_count / total) if total > 0 else 0.0
                            
                            suggestions.append({
                                "by": new_by, "value": new_val, "score": rate,
                                "source": f"kb_{str(src_type).lower() if src_type else 'auto'}"
                            })
                        
                        if suggestions:
                            logger.info(f"[Suggestion] Found {len(suggestions)} candidates from KB (Variant B).")
                    except Exception as e:
                        logger.debug(f"[Suggestion] KB Query Variant B Error: {e}")

        except Exception as e:
            logger.error(f"[Suggestion] Connection Error: {e}")
        finally:
            if temp_conn:
                try: temp_conn.close()
                except: pass

        return suggestions

    def update_knowledge(self, old_locator, new_locator, fingerprint, commit_info, page_url=None, engine="PYTHON", score=None, duration_ms=0):
        if not self.enabled: return
        fp_hash = _fingerprint_hash(fingerprint)
        
        try:
            if self.conn.closed: self.conn = psycopg2.connect(**self.db_config)
            with self.conn.cursor() as cur:
                project_id = self._resolve_project_id(cur, page_url)
                
                # CẬP NHẬT SQL: Sử dụng last_updated và last_seen_at
                insert_sql = f"""
                    INSERT INTO {PUBLIC_KB_TABLE} (
                        project_id, fingerprint, fingerprint_hash, fingerprint_json,
                        old_locator_by, old_locator_value, new_locator_by, new_locator_value,
                        success_count, failure_count, success_rate, last_engine, last_score,
                        avg_repair_ms, last_success_at, last_updated, last_seen_at, source_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 0, %s, %s, %s, %s, NOW(), NOW(), NOW(), 'AUTO')
                    ON CONFLICT ON CONSTRAINT uq_kb 
                    DO UPDATE SET
                        success_count = {PUBLIC_KB_TABLE}.success_count + 1,
                        last_score = EXCLUDED.last_score,
                        avg_repair_ms = ({PUBLIC_KB_TABLE}.avg_repair_ms + EXCLUDED.avg_repair_ms) / 2,
                        last_seen_at = NOW(),
                        last_updated = NOW();
                """
                cur.execute(insert_sql, (
                    project_id, 
                    psycopg2.extras.Json(fingerprint), 
                    fp_hash, 
                    psycopg2.extras.Json(fingerprint),
                    old_locator[0], old_locator[1], 
                    new_locator[0], new_locator[1],
                    float(score * 100) if score else 0.0,
                    engine, score, duration_ms
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"[KB Client] Update Knowledge failed: {e}")
            self.conn.rollback()
    # ---------------------------------------------------------
    # Wrapper for Manager
    # ---------------------------------------------------------
    def save_healing_result(self, payload: Dict[str, Any]):
        self.update_knowledge(
            old_locator=(payload['old_locator_by'], payload['old_locator_value']),
            new_locator=(payload['new_locator_by'], payload['new_locator_value']),
            fingerprint=payload['fingerprint_json'],
            commit_info={},
            engine=payload['last_engine'],
            score=payload['last_score'],
            duration_ms=payload['avg_repair_ms']
        )
    def __del__(self):
        if self.conn and not self.conn.closed:
            try:
                self.conn.close()
            except: pass