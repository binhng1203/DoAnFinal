import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

import psycopg2
from psycopg2.extras import Json, RealDictCursor

# Giả sử import HealingContext và StorageService từ project của bạn
from ..context import HealingContext
from .storage_service import StorageService

logger = logging.getLogger(__name__)

SCHEMA = "custom_analytics"

KB_TABLE = "public.healing_knowledge"
HEAL_EVENT_TABLE = f"{SCHEMA}.heal_event"
TEST_RUN_HISTORY_TABLE = f"{SCHEMA}.test_run_history"
LOCATOR_INSTABILITY_TABLE = f"{SCHEMA}.locator_instability"
VISUAL_VALIDATION_TABLE = f"{SCHEMA}.visual_validation_event"


class PersistenceService:
    """
    PersistenceService quản lý việc lưu trữ log, history vào DB Report 
    và truy vấn dữ liệu từ DB Healenium gốc.
    """

    def __init__(self, db_config: Dict[str, Any]):
        self.conn = None
        self.storage_service: Optional[StorageService] = None

        # 1. Kết nối DB
        try:
            cfg = {**db_config}
            cfg.setdefault("host", os.environ.get("REPORT_DB_HOST", "localhost"))
            cfg["port"] = int(cfg.get("port", os.environ.get("REPORT_DB_PORT", 5432)))
            cfg.setdefault("dbname", os.environ.get("REPORT_DB_NAME", "final"))
            cfg.setdefault("user", os.environ.get("REPORT_DB_USER", "postgres"))
            cfg.setdefault(
                "password",
                os.environ.get("REPORT_DB_PASSWORD", "postgres"),
            )

            self.conn = psycopg2.connect(**cfg)
            self.conn.autocommit = False

            with self.conn.cursor() as cur:
                # Set search_path để ưu tiên schema custom_analytics và healenium
                cur.execute(f"SET search_path TO {SCHEMA}, healenium, public;")
            self.conn.commit()

            logger.info("[PersistenceService] Kết nối PostgreSQL (báo cáo) thành công.")

        except psycopg2.OperationalError as e:
            logger.error(f"[PersistenceService] Không thể kết nối PostgreSQL: {e}")
            self.conn = None
        except Exception as e:
            logger.error(f"[PersistenceService] Lỗi khởi tạo: {e}")
            self.conn = None

        # 2. Khởi tạo StorageService (Upload ảnh)
        try:
            base_public_url = os.getenv(
                "VISUAL_BASE_URL", "http://localhost:8000/static/visual"
            )
            base_dir = os.getenv(
                "VISUAL_BASE_DIR", os.path.join(os.getcwd(), "visual_public")
            )
            self.storage_service = StorageService(
                base_public_url=base_public_url, base_dir=base_dir
            )
            logger.info(
                f"[PersistenceService] StorageService sẵn sàng. BASE_URL={base_public_url}"
            )
        except Exception as e:
            logger.error(
                f"[PersistenceService] Không thể khởi tạo StorageService: {e}",
                exc_info=True,
            )
            self.storage_service = None

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    @staticmethod
    def _now_utc() -> datetime:
        return datetime.utcnow()

    def _fingerprint_hash(self, fingerprint: Dict[str, Any]) -> Optional[str]:
        if not fingerprint or not isinstance(fingerprint, dict):
            return None
        try:
            s = json.dumps(fingerprint, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(s.encode("utf-8")).hexdigest()
        except Exception:
            return None

    def _extract_test_context(self, context: HealingContext) -> Dict[str, Any]:
        tc = getattr(context, "test_context", {}) or {}
        if isinstance(tc, dict):
            return tc
        return {
            "test_id": getattr(tc, "test_id", "unknown_test"),
            "run_id": getattr(tc, "run_id", None),
            "page_url": getattr(tc, "page_url", None),
            "app_version": getattr(tc, "app_version", None),
        }

    @staticmethod
    def _fmt_locator(by: Any, value: Any) -> str:
        return f"{by}={value}"

    # ----------------------------------------------------------------------
    # 1) API cho DecisionLayer + test runner
    # ----------------------------------------------------------------------
    def load_history_for_test(self, test_id: str) -> List[Dict[str, Any]]:
        if not self.conn:
            return []
        query = f"""
            SELECT *
            FROM {TEST_RUN_HISTORY_TABLE}
            WHERE test_id = %s
            ORDER BY timestamp ASC
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (test_id,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"[PersistenceService] load_history_for_test lỗi: {e}")
            if self.conn:
                self.conn.rollback()
            return []

    def save_raw_run_and_get_id(
        self, test_id: str, app_version: str | None = None
    ) -> Optional[int]:
        if not self.conn:
            return None

        log_entry = {
            "test_id": test_id,
            "timestamp": self._now_utc().isoformat(),
            "raw_result": "N/A",
            "heal_attempted": False,
            "heal_success": False,
            "final_result": "Running",
            "calculated_risk": None,
            "total_duration_ms": None,
            "total_heal_attempts": 0,
            "total_heal_success": 0,
            "app_version": app_version,
        }

        query = f"""
            INSERT INTO {TEST_RUN_HISTORY_TABLE} (
                test_id, timestamp, raw_result,
                heal_attempted, heal_success, final_result,
                calculated_risk, total_duration_ms,
                total_heal_attempts, total_heal_success, app_version
            )
            VALUES (
                %(test_id)s, %(timestamp)s, %(raw_result)s,
                %(heal_attempted)s, %(heal_success)s, %(final_result)s,
                %(calculated_risk)s, %(total_duration_ms)s,
                %(total_heal_attempts)s, %(total_heal_success)s, %(app_version)s
            )
            RETURNING id;
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, log_entry)
                run_id = cur.fetchone()[0]
            self.conn.commit()
            return run_id
        except Exception as e:
            logger.error(f"[PersistenceService] save_raw_run_and_get_id lỗi: {e}")
            if self.conn:
                self.conn.rollback()
            return None

    def _update_run_history_on_heal_status(
        self, run_id: int, heal_status: str, risk_score: float | None = None
    ):
        if not self.conn:
            return

        heal_success = heal_status == "SUCCESS"
        try:
            with self.conn.cursor() as cur:
                update_sql = f"""
                    UPDATE {TEST_RUN_HISTORY_TABLE}
                    SET
                        raw_result = 'Fail',
                        heal_attempted = TRUE,
                        heal_success = %s,
                        calculated_risk = COALESCE(%s, calculated_risk),
                        total_heal_attempts = total_heal_attempts + 1,
                        total_heal_success  = total_heal_success + %s
                    WHERE id = %s;
                """
                cur.execute(
                    update_sql,
                    (heal_success, risk_score, 1 if heal_success else 0, run_id),
                )
            self.conn.commit()
        except Exception as e:
            logger.error(
                f"[PersistenceService] _update_run_history_on_heal_status lỗi: {e}"
            )
            if self.conn:
                self.conn.rollback()

    def update_run_history_final_status(
        self, run_id: int, final_status: str, total_duration_ms: int | None = None
    ):
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                update_sql = f"""
                    UPDATE {TEST_RUN_HISTORY_TABLE}
                    SET
                        final_result      = %s,
                        total_duration_ms = COALESCE(%s, total_duration_ms),
                        raw_result = CASE
                            WHEN total_heal_attempts = 0
                                 AND %s = 'Pass'
                                 AND raw_result = 'N/A'
                            THEN 'Pass'
                            ELSE raw_result
                        END
                    WHERE id = %s;
                """
                cur.execute(
                    update_sql, (final_status, total_duration_ms, final_status, run_id)
                )
            self.conn.commit()
        except Exception as e:
            logger.error(
                f"[PersistenceService] update_run_history_final_status lỗi: {e}"
            )
            if self.conn:
                self.conn.rollback()

    # ----------------------------------------------------------------------
    # 2) Upsert Knowledge Base: public.healing_knowledge
    # ----------------------------------------------------------------------
    def _upsert_kb(
        self,
        fingerprint: Dict[str, Any],
        old_locator: Tuple[str, str],
        new_locator: Tuple[str, str] | None,
        success: bool,
        duration_ms: int | None,
        commit_info: Dict[str, Any] | None,
        app_version: str | None,
        project_id: int | None = None,
        source_type: str = "AUTO",
    ):
        if not self.conn:
            return

        old_by, old_val = old_locator
        new_by, new_val = new_locator if new_locator else ("", "")

        succ_inc = 1 if success else 0
        fail_inc = 0 if success else 1
        dur = int(duration_ms or 0)

        sql = f"""
            INSERT INTO {KB_TABLE} (
                project_id, fingerprint,
                old_locator_by, old_locator_value,
                new_locator_by, new_locator_value,
                success_count, failure_count,
                avg_repair_ms,
                last_success_at, last_failure_at,
                commit_info, source_type, app_version
            )
            VALUES (
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (fingerprint, old_locator_value, new_locator_value)
            DO UPDATE SET
                success_count = public.healing_knowledge.success_count + %s,
                failure_count = public.healing_knowledge.failure_count + %s,
                avg_repair_ms = CASE
                    WHEN %s = 1 THEN
                        ((public.healing_knowledge.avg_repair_ms * GREATEST(public.healing_knowledge.success_count,0))
                         + %s)
                        / NULLIF(public.healing_knowledge.success_count + 1, 0)
                    ELSE public.healing_knowledge.avg_repair_ms
                END,
                last_success_at = CASE WHEN %s = 1 THEN NOW() ELSE public.healing_knowledge.last_success_at END,
                last_failure_at = CASE WHEN %s = 1 THEN NOW() ELSE public.healing_knowledge.last_failure_at END,
                commit_info     = COALESCE(EXCLUDED.commit_info, public.healing_knowledge.commit_info),
                app_version     = COALESCE(EXCLUDED.app_version, public.healing_knowledge.app_version),
                last_updated    = NOW();
        """

        params = (
            project_id,
            Json(fingerprint),
            old_by,
            old_val,
            new_by,
            new_val,
            succ_inc,
            fail_inc,
            dur if success else 0,
            self._now_utc() if success else None,
            self._now_utc() if not success else None,
            Json(commit_info or {}),
            source_type,
            app_version,
            succ_inc,
            fail_inc,
            succ_inc,
            dur,
            succ_inc,
            fail_inc,
        )

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()
        except Exception as e:
            logger.error(f"[PersistenceService] _upsert_kb lỗi: {e}")
            if self.conn:
                self.conn.rollback()

    # ----------------------------------------------------------------------
    # 3) locator_instability
    # ----------------------------------------------------------------------
    def _update_locator_instability(
        self,
        locator_old: str,
        success: bool,
        project_id: int | None = None,
    ):
        if not self.conn:
            return

        project_id_norm = project_id if project_id is not None else 0
        succ_inc = 1 if success else 0
        fail_inc = 0 if success else 1

        sql = f"""
            INSERT INTO {LOCATOR_INSTABILITY_TABLE} (
                project_id, locator_old,
                total_failures, total_success,
                instability_rate,
                last_failed_at, last_success_at
            )
            VALUES (
                %s, %s,
                %s, %s,
                0.00,
                %s, %s
            )
            ON CONFLICT (project_id, locator_old)
            DO UPDATE SET
                total_failures = {LOCATOR_INSTABILITY_TABLE}.total_failures + %s,
                total_success  = {LOCATOR_INSTABILITY_TABLE}.total_success  + %s,
                last_failed_at = CASE WHEN %s = 1 THEN NOW() ELSE {LOCATOR_INSTABILITY_TABLE}.last_failed_at END,
                last_success_at= CASE WHEN %s = 1 THEN NOW() ELSE {LOCATOR_INSTABILITY_TABLE}.last_success_at END,
                instability_rate = ROUND(
                    ({LOCATOR_INSTABILITY_TABLE}.total_failures + %s)::NUMERIC * 100.0
                    / NULLIF(({LOCATOR_INSTABILITY_TABLE}.total_failures + %s)
                           + ({LOCATOR_INSTABILITY_TABLE}.total_success + %s), 0),
                    2
                ),
                updated_at = NOW();
        """

        params = (
            project_id_norm,
            locator_old,
            fail_inc,
            succ_inc,
            self._now_utc() if fail_inc else None,
            self._now_utc() if succ_inc else None,
            fail_inc,
            succ_inc,
            fail_inc,
            succ_inc,
            fail_inc,
            fail_inc,
            succ_inc,
        )

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()
        except Exception as e:
            logger.error(
                f"[PersistenceService] _update_locator_instability lỗi: {e}"
            )
            if self.conn:
                self.conn.rollback()

    # ----------------------------------------------------------------------
    # 4) heal_event insert
    # ----------------------------------------------------------------------
    def _insert_heal_event(
        self,
        context: HealingContext,
        engine: str,
        success: bool,
        locator_old: str,
        locator_new: str | None,
        chosen_source: str | None,
        reason: str | None,
        basis_json: Dict[str, Any] | None,
    ):
        if not self.conn:
            return

        test_ctx = self._extract_test_context(context)
        test_id = test_ctx.get("test_id", "unknown_test")
        run_id = test_ctx.get("run_id")
        page_url = getattr(context, "page_url", test_ctx.get("page_url"))
        app_version = test_ctx.get("app_version")

        started_at = getattr(context, "healing_started_at", None) or self._now_utc()
        ended_at = self._now_utc()
        
        confidence = getattr(context, "confidence_of_chosen", None)
        risk_score = getattr(context, "risk_score", None)
        threshold = getattr(context, "adaptive_threshold", None)

        ssim_score = getattr(context, "last_ssim_score", None)
        visual_status = getattr(context, "visual_validation_status", None)

        status = "SUCCESS" if success else "FAILURE"

        sql = f"""
            INSERT INTO {HEAL_EVENT_TABLE} (
                run_id, test_id, project_id, page_url, app_version,
                engine, locator_old, locator_new, chosen_source,
                confidence, risk_score, threshold,
                ssim_score, visual_status,
                started_at, ended_at,
                native_overhead_ms, python_overhead_ms,
                basis, status, reason
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s
            );
        """

        params = (
            run_id,
            test_id,
            None,
            page_url,
            app_version,
            engine,
            locator_old,
            locator_new,
            chosen_source,
            confidence,
            risk_score,
            threshold,
            ssim_score,
            visual_status,
            started_at,
            ended_at,
            getattr(context, "native_overhead_ms", None),
            getattr(context, "python_overhead_ms", None),
            Json(basis_json or {}),
            status,
            reason,
        )

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()

            if run_id is not None:
                try:
                    self._update_run_history_on_heal_status(
                        run_id=run_id,
                        heal_status="SUCCESS" if success else "FAILURE",
                        risk_score=risk_score,
                    )
                except Exception as e2:
                    logger.error(
                        "[PersistenceService] Lỗi update_run_history_on_heal_status: %s",
                        e2,
                    )

        except Exception as e:
            logger.error(f"[PersistenceService] _insert_heal_event lỗi: {e}")
            if self.conn:
                self.conn.rollback()

    # ----------------------------------------------------------------------
    # 5) visual_validation_event (NEW)
    # ----------------------------------------------------------------------
    def log_visual_validation_event(
        self,
        *,
        test_id: str | None,
        run_id: int | None,
        scope: str,
        target_name: str,
        page_url: str | None,
        status: str,
        ssim_score: float | None = None,
        extra_metrics: Dict[str, Any] | None = None,
        baseline_path: Optional[str] = None,
        current_path: Optional[str] = None,
        diff_path: Optional[str] = None,
    ):
        if not self.conn:
            return

        baseline_url = current_url = diff_url = None

        if self.storage_service:
            try:
                from pathlib import Path
                if baseline_path:
                    baseline_url = self.storage_service.upload_file(Path(baseline_path), scope.lower())
                if current_path:
                    current_url = self.storage_service.upload_file(Path(current_path), scope.lower())
                if diff_path:
                    diff_url = self.storage_service.upload_file(Path(diff_path), scope.lower())
            except Exception as e:
                logger.error(
                    f"[PersistenceService] Upload visual file lỗi: {e}",
                    exc_info=True,
                )

        sql = f"""
            INSERT INTO {VISUAL_VALIDATION_TABLE} (
                test_id, run_id, scope, target_name,
                page_url, status, ssim_score, extra_metrics,
                baseline_url, current_url, diff_url
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            );
        """
        params = (
            test_id, run_id, scope, target_name,
            page_url, status, ssim_score, Json(extra_metrics or {}),
            baseline_url, current_url, diff_url,
        )

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()
            logger.info(
                f"[PersistenceService] Đã log visual_validation_event: "
                f"scope={scope}, target={target_name}, status={status}, ssim={ssim_score}"
            )
        except Exception as e:
            logger.error(f"[PersistenceService] log_visual_validation_event lỗi: {e}")
            if self.conn:
                self.conn.rollback()

    # ----------------------------------------------------------------------
    # PUBLIC API mới cho Manager v1
    # ----------------------------------------------------------------------
    def log_healing_success(
        self,
        context: HealingContext,
        engine: str,
        original_locator: Tuple[str, str],
        healed_locator: Tuple[str, str],
        best_candidate: Dict[str, Any],
        basis_json: Dict[str, Any] | None = None,
    ):
        test_ctx = self._extract_test_context(context)
        locator_old_str = self._fmt_locator(*original_locator)
        locator_new_str = self._fmt_locator(*healed_locator)

        self._insert_heal_event(
            context=context,
            engine=engine,
            success=True,
            locator_old=locator_old_str,
            locator_new=locator_new_str,
            chosen_source=best_candidate.get("source"),
            reason=None,
            basis_json=basis_json,
        )

        fingerprint = getattr(context, "fingerprint", None) or {
            "locator_by": original_locator[0],
            "locator_value": original_locator[1],
            "page_url": test_ctx.get("page_url"),
        }
        commit_info = test_ctx.get("commit_info", {})
        app_version = test_ctx.get("app_version")

        self._upsert_kb(
            fingerprint=fingerprint,
            old_locator=original_locator,
            new_locator=healed_locator,
            success=True,
            duration_ms=getattr(context, "healing_duration_ms", None),
            commit_info=commit_info,
            app_version=app_version,
        )

        self._update_locator_instability(
            locator_old=locator_old_str,
            success=True,
        )
        logger.info("[PersistenceService] Đã lưu heal SUCCESS (workflow mới).")

    def log_healing_failure(
        self,
        context: HealingContext,
        engine: str,
        reason: str,
        basis_json: Dict[str, Any] | None = None,
    ):
        test_ctx = self._extract_test_context(context)
        broken = getattr(context, "broken_locator", ("unknown", "unknown"))
        locator_old_str = self._fmt_locator(*broken)

        self._insert_heal_event(
            context=context,
            engine=engine,
            success=False,
            locator_old=locator_old_str,
            locator_new=None,
            chosen_source=None,
            reason=reason,
            basis_json=basis_json,
        )

        fingerprint = getattr(context, "fingerprint", None) or {
            "locator_by": broken[0],
            "locator_value": broken[1],
            "page_url": test_ctx.get("page_url"),
        }
        commit_info = test_ctx.get("commit_info", {})
        app_version = test_ctx.get("app_version")

        self._upsert_kb(
            fingerprint=fingerprint,
            old_locator=broken,
            new_locator=broken,
            success=False,
            duration_ms=getattr(context, "healing_duration_ms", None),
            commit_info=commit_info,
            app_version=app_version,
        )

        self._update_locator_instability(
            locator_old=locator_old_str,
            success=False,
        )
        logger.info(f"[PersistenceService] Đã lưu heal FAILURE (reason={reason}).")

    def save_healing_event(self, context: HealingContext):
        engine = getattr(context, "engine_used", "PYTHON")
        if engine == "RAW":
            return
        if engine and engine.startswith("BACKEND"):
            engine = "NATIVE"
        
        final_status = getattr(context, "final_status", "FAILURE")

        if final_status == "SUCCESS":
            broken = getattr(context, "broken_locator", None)
            chosen = getattr(context, "chosen_locator", None)
            best_cand = getattr(context, "best_candidate", None)

            if not broken or not chosen or not best_cand:
                self.log_healing_failure(
                    context, engine=engine, reason="MISSING_CONTEXT"
                )
                return

            self.log_healing_success(
                context=context,
                engine=engine,
                original_locator=broken,
                healed_locator=chosen,
                best_candidate=best_cand,
                basis_json=getattr(context, "basis_json", None),
            )
        else:
            self.log_healing_failure(
                context=context,
                engine=engine,
                reason="PIPELINE_FAILED",
                basis_json=getattr(context, "basis_json", None),
            )

    # ----------------------------------------------------------------------
    # 6) [NEW] Query Healenium Database trực tiếp
    # ----------------------------------------------------------------------
    def get_selector_from_healenium_db(self, locator_value: str, only_xpath: bool = False, exact: bool = False):
        """
        Tìm baseline trong healenium.selector.

        - locator_value: chuỗi (hoặc một phần chuỗi) bạn muốn tìm trong field 'value' của JSON locator.
        - only_xpath: nếu True, lọc thêm điều kiện type contains 'xpath'.
        - exact: nếu True thì không bọc wildcard '%' (tìm chính xác), mặc định tìm substring.

        Trả về dict row đầu tiên hoặc None.
        """
        if not self.conn:
            print("❌ [PersistenceService] No DB connection")
            return None

        cursor = None
        try:
            cursor = self.conn.cursor()
            # Detect driver module to decide Postgres (psycopg) vs MySQL (pymysql, mysqlclient)
            conn_module = type(self.conn).__module__ if self.conn else ""
            is_postgres = "psycopg" in conn_module or "pg8000" in conn_module or "psycopg2" in conn_module

            # prepare parameter (wildcard unless exact)
            param = locator_value if exact else f"%{locator_value}%"

            if is_postgres:
                # Use json operator ->> to extract 'value'
                where_parts = ["(locator::json ->> 'value') ILIKE %s"]
                params = [param]
                if only_xpath:
                    where_parts.append("(locator::json ->> 'type') ILIKE %s")
                    params.append("%xpath%")
                where_clause = " AND ".join(where_parts)

                sql = f"""
                    SELECT * FROM healenium.selector
                    WHERE {where_clause}
                    ORDER BY create_date DESC
                    LIMIT 1
                """
            else:
                # MySQL (JSON_EXTRACT + JSON_UNQUOTE)
                where_parts = ["JSON_UNQUOTE(JSON_EXTRACT(locator, '$.value')) LIKE %s"]
                params = [param]
                if only_xpath:
                    where_parts.append("JSON_UNQUOTE(JSON_EXTRACT(locator, '$.type')) LIKE %s")
                    params.append("%xpath%")
                where_clause = " AND ".join(where_parts)

                sql = f"""
                    SELECT * FROM healenium.selector
                    WHERE {where_clause}
                    ORDER BY create_date DESC
                    LIMIT 1
                """

            # Debug prints (giúp debug nếu cần)
            print("🔎 [DB DEBUG] SQL:", sql.strip().replace("\n", " "))
            print("🔎 [DB DEBUG] params:", params)

            cursor.execute(sql, tuple(params))
            row = cursor.fetchone()
            if row and cursor.description:
                cols = [d[0] for d in cursor.description]
                result = dict(zip(cols, row))
                print(f"✅ [DB] Found Baseline UID: {result.get('uid')}")
                return result

            # --- Fallback: nếu không tìm thấy bằng JSON extraction, thử search toàn cột locator (plain text) ---
            print("ℹ️ [DB] No row found with JSON extraction. Trying fallback: plain LIKE on locator column...")
            fallback_param = locator_value if exact else f"%{locator_value}%"
            fallback_sql = "SELECT * FROM healenium.selector WHERE locator LIKE %s ORDER BY create_date DESC LIMIT 1"
            print("🔎 [DB DEBUG] fallback SQL:", fallback_sql, "param:", fallback_param)
            cursor.execute(fallback_sql, (fallback_param,))
            row = cursor.fetchone()
            if row and cursor.description:
                cols = [d[0] for d in cursor.description]
                result = dict(zip(cols, row))
                print(f"✅ [DB] Fallback found Baseline UID: {result.get('uid')}")
                return result

            print("ℹ️ [DB] No selector found.")
            return None

        except Exception as e:
            print(f"❌ [DB Error] {e}")
            return None
        finally:
            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass

    # ----------------------------------------------------------------------
    # 7) [FIXED] Learning Mechanism: Lưu selector khớp với Schema Healenium
    # ----------------------------------------------------------------------
    def save_selector_to_healenium(self, locator_by: str, locator_value: str, node_path_str: str, page_url: str):
        """
        Lưu selector vào bảng healenium.selector.
        Cột: uid, url, class_name, method_name, locator, node_path, create_date, command, enable_healing
        """
        if not self.conn:
            return

        # 1. Chuẩn hóa format JSON
        locator_json = json.dumps({"type": locator_by, "value": locator_value})
        
        # Node Path giả lập
        node_path_data = json.dumps([{
            "tag": "legacy_python", 
            "id": "", 
            "classes": [], 
            "innerText": "",
            "other": {"xpath": node_path_str} 
        }])

        # 2. Tạo UID duy nhất
        hash_input = f"{locator_by}_{locator_value}_{page_url}" 
        selector_uid = hashlib.md5(hash_input.encode('utf-8')).hexdigest()

        # 3. [FIX] Câu lệnh SQL khớp với các cột bạn cung cấp
        # Bỏ cột 'name', thêm 'class_name', 'method_name', 'command', 'enable_healing'
        sql = """
            INSERT INTO healenium.selector (
                uid, url, class_name, method_name, 
                locator, node_path, 
                create_date, command, enable_healing
            )
            VALUES (
                %s, %s, %s, %s, 
                %s, %s, 
                NOW(), %s, %s
            )
            ON CONFLICT (uid) DO UPDATE 
            SET create_date = NOW(); -- Cập nhật thời gian nếu đã tồn tại
        """
        
        # Giá trị giả lập cho các cột Java-specific (vì mình chạy Python)
        dummy_class = class_name
        dummy_method = "find_element"
        dummy_command = "findElement"
        enable_healing = True

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    selector_uid,
                    page_url,
                    dummy_class,
                    dummy_method,
                    locator_json,
                    node_path_data,
                    dummy_command,
                    enable_healing
                ))
            self.conn.commit()
            # logger.info(f"[Persistence] Đã lưu selector: {locator_value}")
        except Exception as e:
            logger.warning(f"[Persistence] Lỗi lưu selector baseline: {e}")
            if self.conn:
                self.conn.rollback()


    def close(self):
        """Đóng kết nối cơ sở dữ liệu."""
        if self.conn:
            try:
                self.conn.close()
                print("INFO:[PersistenceService] Đã đóng kết nối CSDL (báo cáo).")
            except Exception as e:
                print(f"ERROR:[PersistenceService] Lỗi khi đóng kết nối: {e}")