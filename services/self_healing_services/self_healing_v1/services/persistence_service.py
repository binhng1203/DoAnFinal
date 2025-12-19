import os
import json
import hashlib
import logging
from datetime import datetime, timezone 
import time
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
                total_heal_attempts, total_heal_success, app_version,
                run_id 
            )
            VALUES (
                %(test_id)s, %(timestamp)s, %(raw_result)s,
                %(heal_attempted)s, %(heal_success)s, %(final_result)s,
                %(calculated_risk)s, %(total_duration_ms)s,
                %(total_heal_attempts)s, %(total_heal_success)s, %(app_version)s,
                gen_random_uuid()::text
            )
            RETURNING run_id;
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, log_entry)
                run_id = cur.fetchone()[0]
            self.conn.commit()
            return run_id
        except Exception as e:
            logger.error(f"[Persistence] save_raw_run lỗi: {e}")
            if self.conn: self.conn.rollback()
            return None
        
    def _update_run_history_on_heal_status(self, run_id: str, heal_status: str, risk_score: float | None = None):
        if not self.conn: return

        heal_success = (heal_status == "SUCCESS")
        try:
            with self.conn.cursor() as cur:
                update_sql = f"""
                    UPDATE {TEST_RUN_HISTORY_TABLE}
                    SET
                        raw_result = 'FAILED',
                        heal_attempted = TRUE,
                        heal_success = %s,
                        calculated_risk = GREATEST(COALESCE(%s, 0), calculated_risk),
                        total_heal_attempts = total_heal_attempts + 1,
                        total_heal_success  = total_heal_success + %s
                    WHERE run_id = %s;
                """
                cur.execute(update_sql, (heal_success, risk_score, 1 if heal_success else 0, run_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"[Persistence] _update_run_history lỗi: {e}")
            if self.conn: self.conn.rollback()

    def finish_test_run(self, run_id: str, test_id: str, start_time: datetime, final_status_from_runner: str = None):
        """
        [FIXED] Tự động xử lý Timezone để tránh lỗi TypeError khi tính duration.
        """
        if not self.conn: return

        # 1. Lấy thời gian kết thúc (Có Timezone UTC)
        end_time = datetime.now(timezone.utc)

        # 2. [QUAN TRỌNG] Kiểm tra start_time đầu vào
        # Nếu start_time không có timezone (naive), ta ép nó thành UTC để khớp với end_time
        if start_time.tzinfo is None:
             start_time = start_time.replace(tzinfo=timezone.utc)
             
        # 3. Tính toán (Giờ cả 2 đều đã có timezone nên trừ được bình thường)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        final_res = final_status_from_runner if final_status_from_runner else "PASSED"

        sql = f"""
            UPDATE {TEST_RUN_HISTORY_TABLE}
            SET
                total_duration_ms = %s,
                final_result = %s,
                raw_result = CASE 
                    WHEN raw_result = 'N/A' OR raw_result IS NULL THEN 'PASSED'
                    ELSE raw_result
                END
            WHERE run_id = %s;
        """

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (duration_ms, final_res, run_id))
            self.conn.commit()
            logger.info(f"[Persistence] Đã chốt sổ run_id={run_id}, duration={duration_ms}ms, final={final_res}")
        except Exception as e:
            logger.error(f"[Persistence] finish_test_run lỗi: {e}")
            self.conn.rollback()

    def update_run_history_final_status(self, run_id: str, final_status: str, total_duration_ms: int | None = None):
        # Wrapper đơn giản gọi finish_test_run hoặc update trực tiếp
        if not self.conn: return
        try:
            with self.conn.cursor() as cur:
                sql = f"""
                    UPDATE {TEST_RUN_HISTORY_TABLE}
                    SET final_result = %s, total_duration_ms = COALESCE(%s, total_duration_ms)
                    WHERE run_id = %s
                """
                cur.execute(sql, (final_status, total_duration_ms, run_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"update_final_status lỗi: {e}")
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
        project_id: str | None = None,
        source_type: str = "AUTO",
    ):
        if not self.conn: return

        # 1. Tính Fingerprint Hash (Để dùng cho ON CONFLICT thay vì dùng JSON raw)
        # Sắp xếp keys để đảm bảo {"a":1, "b":2} giống {"b":2, "a":1}
        try:
            fp_str = json.dumps(fingerprint, sort_keys=True, ensure_ascii=False)
            fingerprint_hash = hashlib.md5(fp_str.encode("utf-8")).hexdigest()
        except Exception:
            fingerprint_hash = "unknown_hash"

        old_by, old_val = old_locator
        new_by, new_val = new_locator if new_locator else ("", "")
        succ_inc = 1 if success else 0
        fail_inc = 0 if success else 1
        dur = int(duration_ms or 0)

        # 2. Cập nhật SQL: Thêm cột fingerprint_hash và sửa ON CONFLICT
        sql = f"""
            INSERT INTO {KB_TABLE} (
                project_id, fingerprint, fingerprint_hash,
                old_locator_by, old_locator_value,
                new_locator_by, new_locator_value,
                success_count, failure_count, avg_repair_ms,
                last_success_at, last_failure_at,
                commit_info, source_type
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            
            -- [FIX] Dùng fingerprint_hash thay vì fingerprint (json)
            ON CONFLICT (fingerprint_hash, old_locator_value, new_locator_value)
            
            DO UPDATE SET
                success_count = public.healing_knowledge.success_count + %s,
                failure_count = public.healing_knowledge.failure_count + %s,
                avg_repair_ms = CASE WHEN %s = 1 THEN 
                    ((public.healing_knowledge.avg_repair_ms * GREATEST(public.healing_knowledge.success_count,0)) + %s) 
                    / NULLIF(public.healing_knowledge.success_count + 1, 0)
                    ELSE public.healing_knowledge.avg_repair_ms END,
                last_success_at = CASE WHEN %s = 1 THEN NOW() ELSE public.healing_knowledge.last_success_at END,
                last_failure_at = CASE WHEN %s = 1 THEN NOW() ELSE public.healing_knowledge.last_failure_at END,
                commit_info     = COALESCE(EXCLUDED.commit_info, public.healing_knowledge.commit_info),
                last_updated    = NOW();
        """
        
        params = (
            str(project_id) if project_id else None, 
            Json(fingerprint), 
            fingerprint_hash, # Tham số mới
            old_by, old_val, new_by, new_val,
            succ_inc, fail_inc, dur if success else 0,
            self._now_utc() if success else None, self._now_utc() if not success else None,
            Json(commit_info or {}), source_type,
            # Params for UPDATE
            succ_inc, fail_inc, succ_inc, dur, succ_inc, fail_inc
        )

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()
            # logger.info(f"[Persistence] Upsert KB thành công: {fingerprint_hash}")
        except Exception as e:
            logger.error(f"[Persistence] _upsert_kb lỗi: {e}")
            if self.conn: self.conn.rollback()
    def _update_locator_instability(self, locator_old: str, success: bool, project_id: str | None = None):
        """
        Cập nhật thống kê độ mất ổn định của locator.
        Sử dụng cơ chế UPSERT để tự động tính toán instability_rate.
        """
        if not self.conn:
            logger.warning("[Persistence] Không có kết nối DB, bỏ qua update instability.")
            return

        # 1. Chuẩn bị dữ liệu tăng thêm
        fail_inc = 0 if success else 1
        succ_inc = 1 if success else 0
        now = datetime.now()

        # 2. Câu lệnh SQL UPSERT
        # Chúng ta tính toán instability_rate trực tiếp trong DB để đảm bảo tính chính xác
        sql = f"""
            INSERT INTO custom_analytics.locator_instability (
                project_id, locator_old, total_failures, total_success,
                instability_rate, last_failed_at, last_success_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (locator_old) 
            DO UPDATE SET
                total_failures = locator_instability.total_failures + EXCLUDED.total_failures,
                total_success  = locator_instability.total_success  + EXCLUDED.total_success,
                last_failed_at = COALESCE(EXCLUDED.last_failed_at, locator_instability.last_failed_at),
                last_success_at = COALESCE(EXCLUDED.last_success_at, locator_instability.last_success_at),
                updated_at = NOW(),
                -- Công thức tính Rate: (Fail / Total) * 100
                instability_rate = ROUND(
                    (CAST(locator_instability.total_failures + EXCLUDED.total_failures AS NUMERIC) * 100.0) / 
                    NULLIF(
                        (locator_instability.total_failures + EXCLUDED.total_failures) + 
                        (locator_instability.total_success + EXCLUDED.total_success), 0
                    ), 2
                );
        """

        # 3. Chuẩn bị tuple tham số (Khớp 100% với số dấu %s trong phần VALUES)
        # Các giá trị trong EXCLUDED sẽ được lấy từ phần VALUES này
        initial_rate = 0.0 if success else 100.0
        params = (
            project_id or "default_project",
            locator_old,
            fail_inc,
            succ_inc,
            initial_rate,
            now if not success else None, # last_failed_at
            now if success else None      # last_success_at
        )

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()
            logger.debug(f"[Persistence] Updated instability for: {locator_old}")
        except Exception as e:
            if self.conn: self.conn.rollback()
            logger.error(f"[Persistence] Lỗi cập nhật locator_instability: {e}")

    def get_locator_instability(self, locator_value: str) -> float:
        """Lấy tỷ lệ mất ổn định của locator từ DB."""
        if not self.conn: return 0.0
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT instability_rate FROM custom_analytics.locator_instability WHERE locator_old = %s",
                    (locator_value,)
                )
                row = cur.fetchone()
                return float(row[0]) if row else 0.0
        except:
            return 0.0
    # ----------------------------------------------------------------------
    # 4) heal_event insert (Đã sửa để khớp schema DB và thêm logic nghiệp vụ)
    # ----------------------------------------------------------------------
    def _insert_heal_event(
        self, context: HealingContext, engine: str, success: bool,
        locator_old: str, locator_new: str | None, chosen_source: str | None,
        reason: str | None, basis_json: Dict[str, Any] | None,
    ):
        if not self.conn: return

        test_ctx = self._extract_test_context(context)
        run_id = test_ctx.get("run_id")
        
        started_at = getattr(context, "healing_started_at", None) or self._now_utc()
        duration_ms = int((self._now_utc() - started_at).total_seconds() * 1000)

        final_source = "UNKNOWN"
        if chosen_source:
            if any(k in chosen_source.lower() for k in ["suggestion", "kb"]): final_source = "KB"
            elif any(k in chosen_source.lower() for k in ["database", "db", "healenium"]): final_source = "DB"
            else: final_source = chosen_source

        sql = f"""
            INSERT INTO {HEAL_EVENT_TABLE} (
                run_id, test_id, project_id, page_url,
                locator_old, locator_new, engine, chosen_source,
                confidence, risk_score, threshold,
                ssim_score, visual_status, status, error_message,
                started_at, duration_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        
        params = (
            run_id, test_ctx.get("test_id", "unknown"), None, getattr(context, "page_url", None),
            locator_old, locator_new, engine, final_source,
            getattr(context, "confidence_of_chosen", 0.0), getattr(context, "risk_score", 0.0),
            getattr(context, "adaptive_threshold", 0.0), getattr(context, "last_ssim_score", 0.0),
            getattr(context, "visual_validation_status", "UNKNOWN"),
            "SUCCESS" if success else "FAILURE", reason, started_at, duration_ms
        )

        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
            self.conn.commit()
            
            if run_id:
                self._update_run_history_on_heal_status(run_id, "SUCCESS" if success else "FAILURE", getattr(context, "risk_score", 0.0))
        except Exception as e:
            logger.error(f"[Persistence] _insert_heal_event lỗi: {e}")
            if self.conn: self.conn.rollback()
    # ----------------------------------------------------------------------
    # 5) visual_validation_event (NEW)
    # ----------------------------------------------------------------------
    def log_visual_validation_event(
        self, *, test_id: str | None, run_id: str | None, scope: str,
        target_name: str, page_url: str | None, status: str,
        ssim_score: float | None = None, extra_metrics: Dict[str, Any] | None = None,
        baseline_path: str = None, current_path: str = None, diff_path: str = None,
    ):
        if not self.conn: return

        b_url = c_url = d_url = None
        if self.storage_service:
            from pathlib import Path
            try:
                if baseline_path: b_url = self.storage_service.upload_file(Path(baseline_path), scope.lower())
                if current_path: c_url = self.storage_service.upload_file(Path(current_path), scope.lower())
                if diff_path: d_url = self.storage_service.upload_file(Path(diff_path), scope.lower())
            except Exception as e:
                logger.error(f"[Persistence] Upload visual error: {e}")

        sql = f"""
            INSERT INTO {VISUAL_VALIDATION_TABLE} (
                test_id, run_id, scope, target_name,
                page_url, status, ssim_score, extra_metrics,
                baseline_path, current_path, diff_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, (
                    test_id, run_id, scope, target_name, page_url, status, ssim_score,
                    Json(extra_metrics or {}), b_url, c_url, d_url
                ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"[Persistence] log_visual_validation_event lỗi: {e}")
            if self.conn: self.conn.rollback()

    # ----------------------------------------------------------------------
    # PUBLIC API mới cho Manager v1
    # ----------------------------------------------------------------------
    def log_healing_success(self, context: HealingContext, engine: str, original_locator: Tuple[str, str], healed_locator: Tuple[str, str], best_candidate: Dict[str, Any], basis_json: Dict[str, Any] | None = None):
        self._insert_heal_event(
            context, engine, True, self._fmt_locator(*original_locator), self._fmt_locator(*healed_locator),
            best_candidate.get("source"), None, basis_json
        )
        
        # Update KB & Instability
        t_ctx = self._extract_test_context(context)
        fingerprint = getattr(context, "fingerprint", None)
        if not fingerprint:
            fingerprint = {"locator_by": original_locator[0], "locator_value": original_locator[1], "page_url": t_ctx.get("page_url")}

        self._upsert_kb(
            fingerprint, original_locator, healed_locator, True,
            getattr(context, "healing_duration_ms", 0), t_ctx.get("commit_info", {}),
            t_ctx.get("app_version"), t_ctx.get("project_id")
        )
        self._update_locator_instability(self._fmt_locator(*original_locator), True)

    def log_healing_failure(self, context: HealingContext, engine: str, reason: str, basis_json: Dict[str, Any] | None = None):
        broken = getattr(context, "broken_locator", ("unknown", "unknown"))
        self._insert_heal_event(
            context, engine, False, self._fmt_locator(*broken), None, None, reason, basis_json
        )
        # Update Instability
        self._update_locator_instability(self._fmt_locator(*broken), False)

    def save_healing_event(self, context: HealingContext):
        # Dispatcher function
        if getattr(context, "final_status", "FAILURE") == "SUCCESS":
            if context.broken_locator and context.chosen_locator:
                best = getattr(context, "best_candidate", {}) or {"source": getattr(context, "source_of_chosen", "UNKNOWN")}
                self.log_healing_success(context, "PYTHON", context.broken_locator, context.chosen_locator, best)
        else:
            self.log_healing_failure(context, "PYTHON", "Pipeline Failed")
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