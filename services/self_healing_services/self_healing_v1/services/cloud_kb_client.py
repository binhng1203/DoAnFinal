from __future__ import annotations

import json
import hashlib
from datetime import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple

# Import psycopg2 an toàn (nếu chưa cài thư viện thì không crash ngay)
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


def _fingerprint_hash(fp: Dict[str, Any]) -> str:
    """
    Tạo fingerprint_hash: sha256(json_sorted).
    """
    s = json.dumps(fp or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class CloudKnowledgeBaseClient:
    """
    Client tương tác với KB: public.healing_knowledge.
    Hỗ trợ chế độ 'Safe Mode': Nếu không có config DB, tự động disable để không ảnh hưởng luồng chính.
    """

    def __init__(self, db_config: Optional[Dict[str, str]] = None):
        self.conn = None
        self.db_config = db_config or {}
        self.enabled = False

        if not DB_AVAILABLE:
            logger.warning("[KB Client] Thư viện 'psycopg2' chưa được cài đặt. KB bị vô hiệu hóa.")
            return

        # Kiểm tra config tối thiểu
        if self.db_config and self.db_config.get('dbname'):
            self.enabled = True
            try:
                self.conn = psycopg2.connect(**self.db_config)
                psycopg2.extras.register_json(self.conn)
                self.conn.autocommit = False
                logger.info(f"[KB Client] Kết nối CSDL '{self.db_config.get('dbname')}' thành công.")
            except Exception as e:
                logger.error(f"[KB Client] Không thể kết nối CSDL (chuyển sang mode Disabled): {e}")
                self.enabled = False
                self.conn = None
        else:
            logger.info("[KB Client] Không có cấu hình DB. Chạy ở chế độ 'Offline' (Disabled).")

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

    # ---------------------------------------------------------
    # Core Functions
    # ---------------------------------------------------------
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

    def update_knowledge(
        self,
        old_locator: Tuple[str, str],
        new_locator: Tuple[str, str],
        fingerprint: Dict[str, Any],
        commit_info: Dict[str, Any],
        page_url: Optional[str] = None,
        engine: str = "PYTHON",
        score: Optional[float] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        
        if not self.enabled or not self.conn:
            return

        old_by, old_val = old_locator
        new_by, new_val = new_locator
        fp_hash = _fingerprint_hash(fingerprint)
        fp_json = psycopg2.extras.Json(fingerprint or {})
        commit_json = psycopg2.extras.Json(commit_info or {})

        try:
            # Re-verify connection
            if self.conn.closed:
                self.conn = psycopg2.connect(**self.db_config)

            with self.conn.cursor() as cur:
                try:
                    cur.execute("SET search_path TO custom_analytics, public;")
                except: pass

                project_id = self._resolve_project_id(cur, page_url)

                # --- Try Variant A Upsert ---
                try:
                    insert_sql = f"""
                    INSERT INTO {PUBLIC_KB_TABLE} (
                        project_id, fingerprint_hash, fingerprint_json,
                        old_locator_by, old_locator_value,
                        new_locator_by, new_locator_value,
                        success_count, failure_count, success_rate,
                        last_engine, last_score, commit_info, 
                        avg_repair_ms, last_success_at, updated_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        1, 0, 100.0,
                        %s, %s, %s,
                        %s, NOW(), NOW()
                    )
                    ON CONFLICT (project_id, fingerprint_hash, old_locator_value, new_locator_value)
                    DO UPDATE SET
                        success_count = {PUBLIC_KB_TABLE}.success_count + 1,
                        success_rate = (CAST({PUBLIC_KB_TABLE}.success_count + 1 AS FLOAT) / ({PUBLIC_KB_TABLE}.success_count + {PUBLIC_KB_TABLE}.failure_count + 1)) * 100,
                        last_success_at = NOW(),
                        last_engine = EXCLUDED.last_engine,
                        last_score = EXCLUDED.last_score,
                        updated_at = NOW();
                    """
                    cur.execute(insert_sql, (
                        project_id, fp_hash, fp_json,
                        old_by, old_val, new_by, new_val,
                        engine, score, commit_json, int(duration_ms or 0)
                    ))
                    self.conn.commit()
                    logger.info(f"[Learning] Updated KB (Variant A): {old_val} -> {new_val}")
                    return
                except (psycopg2.errors.UndefinedColumn, psycopg2.errors.UniqueViolation, psycopg2.errors.InFailedSqlTransaction):
                    self.conn.rollback()
                    logger.debug("[Learning] Variant A insert failed, trying Variant B...")
                
                # --- Try Variant B Upsert ---
                try:
                    insert_sql_b = f"""
                    INSERT INTO {PUBLIC_KB_TABLE} (
                        project_id, fingerprint,
                        old_locator_by, old_locator_value,
                        new_locator_by, new_locator_value,
                        success_count, failure_count,
                        source_type, commit_info, last_success_at, last_updated
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, 1, 0,
                        %s, %s, NOW(), NOW()
                    )
                    ON CONFLICT (fingerprint, old_locator_value, new_locator_value)
                    DO UPDATE SET
                        success_count = {PUBLIC_KB_TABLE}.success_count + 1,
                        last_success_at = NOW(),
                        last_updated = NOW();
                    """
                    cur.execute(insert_sql_b, (
                        project_id, fp_json,
                        old_by, old_val, new_by, new_val,
                        engine, commit_json
                    ))
                    self.conn.commit()
                    logger.info(f"[Learning] Updated KB (Variant B): {old_val} -> {new_val}")
                except Exception as e:
                    self.conn.rollback()
                    logger.error(f"[Learning] All insert attempts failed: {e}")

        except Exception as e:
            logger.error(f"[Learning] Connection error during update: {e}")

    # ---------------------------------------------------------
    # Wrapper for Manager
    # ---------------------------------------------------------
    def save_mapping(
        self,
        page_url: Optional[str],
        broken_by: str,
        broken_value: str,
        healed_by: str,
        healed_value: str,
        source: str,
        score: float,
        duration_ms: Optional[int] = None,
        commit_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """API wrapper cho HealingManager"""
        if not self.enabled: return

        fingerprint = {
            "locator_by": broken_by,
            "locator_value": broken_value,
            "page_url": page_url,
        }
        
        self.update_knowledge(
            old_locator=(broken_by, broken_value),
            new_locator=(healed_by, healed_value),
            fingerprint=fingerprint,
            commit_info=commit_info or {},
            page_url=page_url,
            engine=source,
            score=score,
            duration_ms=duration_ms
        )

    def __del__(self):
        if self.conn and not self.conn.closed:
            try:
                self.conn.close()
            except: pass