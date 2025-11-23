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

    H02:
      - get_suggestions(fingerprint, page_url=None)
        -> trả list candidates dạng {by, value, score, source}

    H03:
      - update_knowledge(old_locator, new_locator, fingerprint, commit_info, ...)
        -> upsert vào healing_knowledge (success_count++, update stats)

    Lưu ý:
      - healing_knowledge là KB CHUNG (native + python đều đổ vào).
      - manual_override_mapping nếu có sẽ được ưu tiên trả về trước.
    """

    def __init__(self, db_config: Dict[str, str]):
        self.conn = None
        try:
            self.conn = psycopg2.connect(**db_config)
            psycopg2.extras.register_json(self.conn)
            self.conn.autocommit = False
            logger.info(f"[KB Client] Kết nối CSDL '{db_config.get('dbname')}' thành công.")
        except Exception as e:
            logger.error(f"[KB Client] Không thể kết nối CSDL: {e}")
            self.conn = None

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _resolve_project_id(self, cursor, page_url: Optional[str]) -> Optional[int]:
        if not page_url:
            return None
        try:
            cursor.execute(
                f"SELECT id FROM {PROJECT_TABLE} WHERE base_url=%s OR project_name=%s LIMIT 1;",
                (page_url, page_url),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None
        except Exception:
            return None

    # ---------------------------------------------------------
    # H02
    # ---------------------------------------------------------
    def get_suggestions(
        self,
        fingerprint: Dict[str, Any],
        page_url: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Query KB theo fingerprint_hash (+ project nếu resolve được).

        Trả về candidates:
          [{by, value, score, source}]
        """
        if not self.conn:
            logger.error("[H02] Không có kết nối CSDL.")
            return []

        fp_hash = _fingerprint_hash(fingerprint)
        suggestions: List[Dict[str, Any]] = []

        try:
            with self.conn.cursor() as cur:
                cur.execute("SET search_path TO custom_analytics, public;")

                project_id = self._resolve_project_id(cur, page_url)

                # 1) Ưu tiên manual override nếu có
                if project_id is not None:
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
                        by_new, val_new = loc_new.split("=", 1)
                        suggestions.append(
                            {
                                "by": by_new.strip(),
                                "value": val_new.strip(),
                                "score": 1.0,  # override coi như chắc chắn nhất
                                "source": "manual_override",
                            }
                        )
                    if suggestions:
                        logger.info(f"[H02] Trả về {len(suggestions)} gợi ý từ manual_override.")
                        return suggestions

                # 2) Query KB chính
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
                    # convert success_rate (%) về 0-1 làm score tham khảo nếu last_score None
                    score = float(last_score) if last_score is not None else float(success_rate) / 100.0
                    suggestions.append(
                        {
                            "by": new_by,
                            "value": new_val,
                            "score": score,
                            "source": f"kb_{str(last_engine).lower()}",
                            "success_rate": float(success_rate),
                            "success_count": int(success_count),
                        }
                    )

            if suggestions:
                logger.info(f"[H02] Tìm thấy {len(suggestions)} gợi ý trong healing_knowledge.")
            else:
                logger.info("[H02] Không tìm thấy gợi ý nào trong healing_knowledge.")

        except Exception as e:
            logger.error(f"[H02] Lỗi khi truy vấn KB: {e}")
            if self.conn:
                self.conn.rollback()

        return suggestions

    # ---------------------------------------------------------
    # H03 (API cũ) -> upsert vào healing_knowledge
    # ---------------------------------------------------------
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
        """
        if not self.conn:
            logger.error("[H03] Không có kết nối CSDL.")
            return

        old_by, old_val = old_locator
        new_by, new_val = new_locator
        fp_hash = _fingerprint_hash(fingerprint)

        try:
            with self.conn.cursor() as cur:
                cur.execute("SET search_path TO custom_analytics, public;")

                project_id = self._resolve_project_id(cur, page_url)

                commit_json = psycopg2.extras.Json(commit_info or {})
                fp_json = psycopg2.extras.Json(fingerprint or {})

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

            self.conn.commit()
            logger.info(f"[H03] Cập nhật healing_knowledge OK: {old_val} -> {new_val}")

        except Exception as e:
            logger.error(f"[H03] Lỗi khi update KB: {e}")
            if self.conn:
                self.conn.rollback()

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
