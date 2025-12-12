# self_healing_v1/services/cloud_kb_client.py
from __future__ import annotations

import json
import hashlib
from datetime import datetime
import psycopg2
import psycopg2.extras
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

PUBLIC_KB_TABLE = "public.healing_knowledge"
MANUAL_OVERRIDE_TABLE = "custom_analytics.manual_override_mapping"
PROJECT_TABLE = "custom_analytics.project"


def _fingerprint_hash(fp: Dict[str, Any]) -> str:
    """
    Tạo fingerprint_hash giống PersistenceService:
    sha256(json_sorted).
    """
    s = json.dumps(fp or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class CloudKnowledgeBaseClient:
    """
    Client tương tác với KB mới: public.healing_knowledge
    ...
    """

    def __init__(self, db_config: Dict[str, str]):
        self.conn = None
        self.db_config = db_config  # LƯU LẠI CONFIG để dùng cho separate connections
        try:
            self.conn = psycopg2.connect(**db_config)
            psycopg2.extras.register_json(self.conn)
            self.conn.autocommit = False
            logger.info(f"[KB Client] Kết nối CSDL '{db_config.get('dbname')}' thành công.")
        except Exception as e:
            logger.error(f"[KB Client] Không thể kết nối CSDL: {e}")
            self.conn = None

    # ---------------------------------------------------------
    # Helper: resolve project_id (try DB then deterministic fallback)
    # ---------------------------------------------------------
    def _resolve_project_id(self, cur, page_url: Optional[str] = None) -> Optional[str]:
        """
        Trả về project_id theo thứ tự:
          1) nếu bảng custom_analytics.project tồn tại và có match => trả project_id từ DB
          2) nếu không có bảng hoặc không tìm thấy match => trả deterministic id sinh từ page_url
          3) nếu page_url is None => trả None

        cur: psycopg2 cursor (đang dùng temp_conn hoặc self.conn)
        """
        try:
            # Nếu không có page_url -> không thể map theo URL
            if not page_url:
                return None

            # 1) Kiểm tra nếu bảng project tồn tại -> try lookup
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
                try:
                    # Try to match by base_url or url_patterns. Adjust to your project's schema.
                    # First try hostname-based match if base_url column present
                    from urllib.parse import urlparse
                    host = urlparse(page_url).netloc
                    if host:
                        # Try match base_url contains host
                        cur.execute(
                            """
                            SELECT project_id
                            FROM custom_analytics.project
                            WHERE base_url IS NOT NULL AND %s ILIKE CONCAT('%', base_url, '%')
                            LIMIT 1;
                            """,
                            (host,),
                        )
                        row = cur.fetchone()
                        if row:
                            return str(row[0])
                    # Fallback: try url_patterns array if present
                    cur.execute(
                        """
                        SELECT project_id
                        FROM custom_analytics.project
                        WHERE url_patterns IS NOT NULL
                          AND %s = ANY(url_patterns)
                        LIMIT 1;
                        """,
                        (page_url,),
                    )
                    row2 = cur.fetchone()
                    if row2:
                        return str(row2[0])
                except Exception:
                    # nếu bảng có schema khác / cột khác -> ignore và fallback
                    pass

            # 2) Nếu không tìm thấy bằng DB, tạo deterministic id từ page_url
            #    (đảm bảo cùng URL -> cùng project_id)
            #    Lấy 8 ký tự đầu của sha256(host_or_url) để làm project_id
            import hashlib
            hash_input = page_url
            try:
                from urllib.parse import urlparse
                parsed = urlparse(page_url)
                # ưu tiên host nếu có
                hash_input = parsed.netloc or page_url
            except Exception:
                hash_input = page_url
            h = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
            # trả project_id ngắn gọn (8 ký tự hex)
            return h[:8]

        except Exception as e:
            # KHÔNG ném exception để caller không bị crash.
            # Log ở mức debug để không spam production logs.
            logger.debug(f"[KB Client] _resolve_project_id failed for page_url={page_url}: {e}")
            return None

    # ---------------------------------------------------------
    import psycopg2.errors

    def get_suggestions(
        self,
        fingerprint: Dict[str, Any],
        page_url: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        fp_hash = _fingerprint_hash(fingerprint)
        suggestions: List[Dict[str, Any]] = []

        temp_conn = None
        try:
            temp_conn = psycopg2.connect(**self.db_config)
            psycopg2.extras.register_json(temp_conn)
            temp_conn.autocommit = True

            with temp_conn.cursor() as cur:
                cur.execute("SET search_path TO custom_analytics, public;")
                project_id = self._resolve_project_id(cur, page_url)

                # Try variant A: assume columns like success_rate, last_score, fingerprint_hash exist
                try:
                    # manual override (if exists) - keep as in current code but guard table existence
                    if project_id is not None:
                        try:
                            cur.execute(
                                """
                                SELECT EXISTS (
                                    SELECT 1 FROM information_schema.tables
                                    WHERE table_schema = 'custom_analytics' AND table_name = %s
                                );
                                """,
                                (MANUAL_OVERRIDE_TABLE.split('.')[-1],),
                            )
                            mo_exists = cur.fetchone()
                            if mo_exists and mo_exists[0]:
                                cur.execute(
                                    f"""
                                    SELECT locator_new
                                    FROM {MANUAL_OVERRIDE_TABLE}
                                    WHERE project_id=%s
                                      AND fingerprint_hash=%s
                                      AND is_active=TRUE
                                    ORDER BY updated_at DESC
                                    LIMIT %s;
                                    """,
                                    (project_id, fp_hash, limit),
                                )
                                rows = cur.fetchall()
                                for (loc_new,) in rows:
                                    try:
                                        by_new, val_new = loc_new.split("=", 1)
                                    except Exception:
                                        continue
                                    suggestions.append({"by": by_new.strip(), "value": val_new.strip(), "score": 1.0, "source": "manual_override"})
                                if suggestions:
                                    logger.info(f"[H02] Trả về {len(suggestions)} gợi ý từ manual_override.")
                                    return suggestions
                        except Exception:
                            logger.debug("[H02] manual_override check failed (variant A) - skipping")

                    # Query KB (variant A)
                    if project_id is not None:
                        query = f"""
                        SELECT new_locator_by, new_locator_value,
                               success_rate, success_count,
                               last_engine, last_score
                        FROM {PUBLIC_KB_TABLE}
                        WHERE project_id=%s AND fingerprint_hash=%s
                        ORDER BY manual_override DESC,
                                 success_rate DESC,
                                 success_count DESC,
                                 last_seen_at DESC
                        LIMIT %s;
                        """
                        cur.execute(query, (project_id, fp_hash, limit))
                    else:
                        query = f"""
                        SELECT new_locator_by, new_locator_value,
                               success_rate, success_count,
                               last_engine, last_score
                        FROM {PUBLIC_KB_TABLE}
                        WHERE fingerprint_hash=%s
                        ORDER BY manual_override DESC,
                                 success_rate DESC,
                                 success_count DESC,
                                 last_seen_at DESC
                        LIMIT %s;
                        """
                        cur.execute(query, (fp_hash, limit))

                    rows = cur.fetchall()
                    for r in rows:
                        new_by, new_val, success_rate, success_count, last_engine, last_score = r
                        score = float(last_score) if last_score is not None else (float(success_rate) / 100.0 if success_rate is not None else (float(success_count) if success_count is not None else 0.0))
                        suggestions.append({
                            "by": new_by,
                            "value": new_val,
                            "score": score,
                            "source": f"kb_{str(last_engine).lower() if last_engine else 'unknown'}",
                            "success_rate": float(success_rate) if success_rate is not None else None,
                            "success_count": int(success_count) if success_count is not None else None,
                        })

                    if suggestions:
                        logger.info(f"[H02] (variant A) found {len(suggestions)} suggestions.")
                        return suggestions

                except psycopg2.errors.UndefinedColumn as e:
                    # Variant A columns not present in this DB schema -> fallback to variant B
                    logger.debug("[H02] KB variant A columns missing, falling back to variant B: %s", e)
                except Exception as e:
                    # other SQL errors in variant A -> log and then fallback
                    logger.debug("[H02] variant A query error, falling back to variant B: %s", e)

                # Variant B: use fingerprint JSONB and the actual columns present in your schema
                try:
                    # manual override - if table exists and uses fingerprint_hash (unlikely), skip if not present
                    if project_id is not None:
                        try:
                            cur.execute(
                                """
                                SELECT EXISTS (
                                    SELECT 1 FROM information_schema.tables
                                    WHERE table_schema = 'custom_analytics' AND table_name = %s
                                );
                                """,
                                (MANUAL_OVERRIDE_TABLE.split('.')[-1],),
                            )
                            mo_exists = cur.fetchone()
                            if mo_exists and mo_exists[0]:
                                # If manual override exists but stores locator_new keyed by fingerprint_hash,
                                # attempt querying by fp_hash; if structure differs, it's okay to fail and continue.
                                cur.execute(
                                    f"""
                                    SELECT locator_new
                                    FROM {MANUAL_OVERRIDE_TABLE}
                                    WHERE project_id=%s
                                      AND fingerprint_hash=%s
                                      AND is_active=TRUE
                                    ORDER BY updated_at DESC
                                    LIMIT %s;
                                    """,
                                    (project_id, fp_hash, limit),
                                )
                                rows = cur.fetchall()
                                for (loc_new,) in rows:
                                    try:
                                        by_new, val_new = loc_new.split("=", 1)
                                    except Exception:
                                        continue
                                    suggestions.append({"by": by_new.strip(), "value": val_new.strip(), "score": 1.0, "source": "manual_override"})
                                if suggestions:
                                    logger.info(f"[H02] Trả về {len(suggestions)} gợi ý từ manual_override (variant B).")
                                    return suggestions
                        except Exception:
                            logger.debug("[H02] manual_override check failed (variant B) - skipping")

                    # Query KB by fingerprint JSONB
                    fp_json = psycopg2.extras.Json(fingerprint or {})
                    if project_id is not None:
                        query = f"""
                        SELECT new_locator_by, new_locator_value,
                               success_count, failure_count,
                               avg_repair_ms, source_type, last_success_at
                        FROM {PUBLIC_KB_TABLE}
                        WHERE project_id=%s AND fingerprint=%s
                        ORDER BY success_count DESC, last_success_at DESC
                        LIMIT %s;
                        """
                        cur.execute(query, (project_id, fp_json, limit))
                    else:
                        query = f"""
                        SELECT new_locator_by, new_locator_value,
                               success_count, failure_count,
                               avg_repair_ms, source_type, last_success_at
                        FROM {PUBLIC_KB_TABLE}
                        WHERE fingerprint=%s
                        ORDER BY success_count DESC, last_success_at DESC
                        LIMIT %s;
                        """
                        cur.execute(query, (fp_json, limit))

                    rows = cur.fetchall()
                    for r in rows:
                        new_by, new_val, success_count, failure_count, avg_repair_ms, source_type, last_success_at = r
                        # compute score from counts if possible
                        try:
                            sc = (float(success_count) / max(1.0, float(success_count) + float(failure_count))) if (success_count is not None and failure_count is not None) else (float(success_count) if success_count is not None else 0.0)
                        except Exception:
                            sc = 0.0
                        suggestions.append({
                            "by": new_by,
                            "value": new_val,
                            "score": sc,
                            "source": f"kb_{(source_type or 'unknown').lower()}",
                            "success_count": int(success_count) if success_count is not None else None,
                            "failure_count": int(failure_count) if failure_count is not None else None,
                        })

                    if suggestions:
                        logger.info(f"[H02] (variant B) Tìm thấy {len(suggestions)} gợi ý trong healing_knowledge.")
                    else:
                        logger.info("[H02] Không tìm thấy gợi ý nào trong healing_knowledge (variant B).")

                except Exception as e:
                    logger.exception(f"[H02] Lỗi khi truy vấn KB (variant B): {e}")

        except Exception as e:
            logger.exception(f"[H02] Lỗi khi truy vấn KB (connection): {e}")
        finally:
            if temp_conn:
                try:
                    temp_conn.close()
                except Exception:
                    pass

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
        """
        Lưu mapping heal thành công vào public.healing_knowledge.
        Thực hiện 2 bước: thử upsert theo schema 'variant A' (fingerprint_hash),
        nếu fail do UndefinedColumn -> fallback sang variant B (fingerprint JSONB).
        """
        if not self.conn:
            logger.error("[H03] Không có kết nối CSDL.")
            return

        old_by, old_val = old_locator
        new_by, new_val = new_locator
        fp_hash = _fingerprint_hash(fingerprint)
        fp_json = psycopg2.extras.Json(fingerprint or {})
        commit_json = psycopg2.extras.Json(commit_info or {})

        try:
            with self.conn.cursor() as cur:
                cur.execute("SET search_path TO custom_analytics, public;")

                project_id = self._resolve_project_id(cur, page_url)

                # Try variant A upsert (the code's original upsert using fingerprint_hash and success_rate)
                try:
                    insert_sql = f"""
                    INSERT INTO {PUBLIC_KB_TABLE} (
                        project_id,
                        fingerprint_hash, fingerprint_json,
                        old_locator_by, old_locator_value,
                        new_locator_by, new_locator_value,
                        success_count, failure_count, success_rate,
                        avg_repair_ms,
                        last_success_at, last_engine, last_score,
                        commit_info, last_seen_at, updated_at
                    ) VALUES (
                        %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        1, 0, 100.00,
                        %s,
                        NOW(), %s, %s,
                        %s, NOW(), NOW()
                    )
                    ON CONFLICT (project_id, fingerprint_hash, old_locator_value, new_locator_value)
                    DO UPDATE SET
                        success_count = {PUBLIC_KB_TABLE}.success_count + 1,
                        last_success_at = NOW(),
                        last_engine = EXCLUDED.last_engine,
                        last_score  = EXCLUDED.last_score,
                        commit_info = EXCLUDED.commit_info,
                        last_seen_at = NOW(),
                        avg_repair_ms = CASE
                            WHEN EXCLUDED.last_score IS NOT NULL AND %s IS NOT NULL THEN
                                (({PUBLIC_KB_TABLE}.avg_repair_ms
                                  * GREATEST({PUBLIC_KB_TABLE}.success_count, 0))
                                  + %s)
                                / NULLIF({PUBLIC_KB_TABLE}.success_count + 1, 0)
                            ELSE {PUBLIC_KB_TABLE}.avg_repair_ms
                        END,
                        updated_at = NOW();
                    """
                    cur.execute(
                        insert_sql,
                        (
                            project_id,
                            fp_hash, fp_json,
                            old_by, old_val,
                            new_by, new_val,
                            int(duration_ms or 0),
                            engine,
                            float(score) if score is not None else None,
                            commit_json,
                            float(score) if score is not None else None,
                            int(duration_ms or 0),
                        ),
                    )
                    # commit for variant A
                    self.conn.commit()
                    logger.info(f"[H03] (variant A) Cập nhật healing_knowledge OK: {old_val} -> {new_val}")
                    return
                except psycopg2.errors.UndefinedColumn:
                    # variant A schema not present - fallback
                    logger.debug("[H03] Variant A columns missing, fallback to variant B.")
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                except Exception as e:
                    # other errors -> log and rollback then continue to variant B
                    logger.exception(f"[H03] variant A insert failed, fallback to variant B: {e}")
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass

                # Variant B: use fingerprint JSONB and simpler columns present in your schema
                try:
                    insert_sql_b = f"""
                    INSERT INTO {PUBLIC_KB_TABLE} (
                        project_id,
                        fingerprint,
                        old_locator_by, old_locator_value,
                        new_locator_by, new_locator_value,
                        success_count, failure_count,
                        avg_repair_ms, last_success_at,
                        source_type, commit_info, last_updated
                    ) VALUES (
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        1, 0,
                        %s, NOW(),
                        %s, %s, NOW()
                    )
                    ON CONFLICT (fingerprint, old_locator_value, new_locator_value)
                    DO UPDATE SET
                        success_count = {PUBLIC_KB_TABLE}.success_count + 1,
                        last_success_at = NOW(),
                        source_type = EXCLUDED.source_type,
                        commit_info = EXCLUDED.commit_info,
                        avg_repair_ms = CASE
                            WHEN EXCLUDED.avg_repair_ms IS NOT NULL THEN
                                (({PUBLIC_KB_TABLE}.avg_repair_ms * GREATEST({PUBLIC_KB_TABLE}.success_count,0)) + EXCLUDED.avg_repair_ms)
                                / NULLIF({PUBLIC_KB_TABLE}.success_count + 1, 0)
                            ELSE {PUBLIC_KB_TABLE}.avg_repair_ms
                        END,
                        last_updated = NOW();
                    """
                    cur.execute(
                        insert_sql_b,
                        (
                            project_id,
                            fp_json,
                            old_by, old_val,
                            new_by, new_val,
                            int(duration_ms or 0),
                            engine,
                            commit_json,
                        ),
                    )
                    self.conn.commit()
                    logger.info(f"[H03] (variant B) Cập nhật healing_knowledge OK: {old_val} -> {new_val}")
                    return
                except Exception as e:
                    logger.exception(f"[H03] variant B insert failed: {e}")
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass

        except Exception as e:
            logger.exception(f"[H03] Unexpected error when updating KB: {e}")
            try:
                if self.conn:
                    self.conn.rollback()
            except Exception:
                pass


    # ---------------------------------------------------------
    # NEW API cho manager v1
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
        """
        Wrapper tiện cho HealingManager v1.
        """
        fingerprint = {
            "locator_by": broken_by,
            "locator_value": broken_value,
            "page_url": page_url,
        }

        meta = commit_info or {}
        meta.update(
            {
                "source": source,
                "score": float(score),
                "saved_at": datetime.utcnow().isoformat(),
            }
        )

        self.update_knowledge(
            old_locator=(broken_by, broken_value),
            new_locator=(healed_by, healed_value),
            fingerprint=fingerprint,
            commit_info=meta,
            page_url=page_url,
            engine="PYTHON" if source != "native" else "NATIVE",
            score=score,
            duration_ms=duration_ms,
        )

    def __del__(self):
        if self.conn:
            try:
                self.conn.close()
                logger.info("[KB Client] Đã đóng kết nối CSDL.")
            except Exception:
                pass
