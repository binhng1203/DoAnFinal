# self_healing_v1/manager.py
import logging
from functools import partial
from typing import Any, Callable, Dict, Optional

from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
)

from .context import HealingContext
from .layers.suggestion_layer import SuggestionLayer
from .layers.healing_layer import HealingLayer
from .layers.decision_layer import DecisionLayer
from .layers.validation_layer import ValidationLayer
from .services.cloud_kb_client import CloudKnowledgeBaseClient
from .services.persistence_service import PersistenceService

logger = logging.getLogger(__name__)


class HealingManager:
    """
    HealingManager điều phối toàn bộ pipeline self-healing PYTHON (Tầng 2).

    TẦNG 1: Healenium native (qua proxy 8085)
    TẦNG 2: Python fallback (4-layer) chỉ chạy khi Tầng 1 thất bại thật sự.
    """

    def __init__(
        self,
        db_config_kb: Dict[str, Any],
        db_config_reporting: Dict[str, Any],
        healenium_host: str = "http://localhost:7878",
        visual_baseline_dir: str = "visual_baseline",
        imitator_url: str = "http://localhost:8000",
        enable_python_fallback: bool = True,   # ✅ cho phép tắt fallback khi cần test native
    ):
        logger.info("Khởi tạo HealingManager (workflow mới)...")

        self.healenium_host = healenium_host
        self.enable_python_fallback = enable_python_fallback

        # ---------- SuggestionLayer (Knowledge Base riêng) ----------
        self.kb_client: Optional[CloudKnowledgeBaseClient] = None
        self.suggestion_layer: Optional[SuggestionLayer] = None
        try:
            self.kb_client = CloudKnowledgeBaseClient(db_config_kb)
            self.suggestion_layer = SuggestionLayer(cloud_kb_client=self.kb_client)
            logger.info("[HealingManager] SuggestionLayer đã sẵn sàng.")
        except Exception as e:
            logger.error(
                f"[HealingManager] Không thể khởi tạo CloudKnowledgeBaseClient hoặc SuggestionLayer: {e}",
                exc_info=True,
            )

        # ---------- Persistence (Báo cáo, analytics) ----------
        self.persistence_service: Optional[PersistenceService] = None
        try:
            self.persistence_service = PersistenceService(db_config_reporting)
            logger.info("[HealingManager] PersistenceService đã sẵn sàng.")
        except Exception as e:
            logger.error(
                f"[HealingManager] Không thể khởi tạo PersistenceService: {e}",
                exc_info=True,
            )

        # ---------- HealingLayer Python (heuristics fallback) ----------
        self.healing_layer = HealingLayer(
            driver=None,
            healenium_host=healenium_host,
        )

        # ---------- Decision & Validation ----------
        self.decision_layer = DecisionLayer(
            persistence_service=self.persistence_service
        )
        self.validation_layer = ValidationLayer(baseline_dir=visual_baseline_dir)

        logger.info(
            "HealingManager đã sẵn sàng (Healenium native qua proxy + 4-layer Python fallback)."
        )

    # ==================================================================
    # Core self-healing pipeline (TẦNG 2)
    # ==================================================================
    def heal(self, context: HealingContext) -> object:
        """
        Thực thi pipeline self-healing (Tầng 2).
        CHỈ chạy khi TẦNG 1 thất bại và fallback được bật.
        """
        context.kb_candidates = getattr(context, "kb_candidates", []) or []
        context.hl_candidates = getattr(context, "hl_candidates", []) or []
        context.all_candidates = getattr(context, "all_candidates", []) or []

        healed_element = None

        try:
            broken_by, broken_value = context.broken_locator

            try:
                if not getattr(context, "page_url", None) and context.driver:
                    context.page_url = context.driver.current_url
            except Exception:
                pass

            # 1) SuggestionLayer
            if self.suggestion_layer:
                kb_candidates = (
                    self.suggestion_layer.get_suggestions(
                        context.broken_locator, context.driver
                    ) or []
                )
                context.fingerprint = self.suggestion_layer.last_fingerprint

                if isinstance(kb_candidates, dict):
                    kb_candidates = [kb_candidates]

                for cand in kb_candidates:
                    cand["source"] = "suggestion_kb"

                context.kb_candidates = kb_candidates
            else:
                logger.warning("[HealingManager] SuggestionLayer không khả dụng.")

            # 2) HealingLayer heuristics
            if self.healing_layer:
                context.hl_candidates = (
                    self.healing_layer.get_candidates(
                        context.driver, broken_by, broken_value
                    ) or []
                )
            else:
                logger.warning("[HealingManager] HealingLayer không khả dụng.")

            # 3) Merge candidates
            context.all_candidates = (context.kb_candidates or []) + (
                context.hl_candidates or []
            )

            if not context.all_candidates:
                raise NoSuchElementException("Self-Healing: Không tìm thấy ứng viên.")

            # 4) DecisionLayer
            decision = self.decision_layer.make_decision(
                context.all_candidates, context.test_context
            )

            context.risk_score = decision.get("risk_score")
            context.adaptive_threshold = decision.get("adaptive_threshold")
            context.decision_status = decision.get("status")

            if decision.get("status") == "REJECTED":
                raise NoSuchElementException(
                    "Self-Healing: DecisionLayer từ chối phục hồi."
                )

            by_final, val_final = decision["chosen_locator"]
            context.chosen_locator = (by_final, val_final)
            context.source_of_chosen = decision.get("source")

            raw_score = decision.get("confidence")
            context.confidence_of_chosen = raw_score
            context.raw_score = raw_score

            context.best_candidate = {
                "by": by_final,
                "value": val_final,
                "score": raw_score,
                "source": decision.get("source"),
                "status": decision.get("status"),
            }

            logger.info(
                f"[HealingManager] (H08) ACCEPTED: {context.chosen_locator} (Score: {raw_score})"
            )

            # 5) find healed element
            healed_element = context.driver.find_element(by_final, val_final)
            context.healed_element = healed_element

            # 6) ValidationLayer
            if self.validation_layer:
                visual_status = self.validation_layer.validate_element(
                    context.healed_element, context.element_name
                )
                context.visual_validation_status = visual_status

                if visual_status == "FAILED":
                    logger.warning(
                        f"[HealingManager] (H11) FAILED: '{context.element_name}' không khớp baseline."
                    )
                elif visual_status == "SOFT_ACCEPT":
                    logger.warning(
                        f"[HealingManager] (H11) SOFT_ACCEPT: '{context.element_name}' hơi lệch baseline nhưng vẫn chấp nhận."
                    )

            # 7) report to KB
            commit_info = (context.test_context or {}).get("commit_info", {}) or {}

            if self.suggestion_layer:
                self.suggestion_layer.report_successful_heal(
                    context.broken_locator,
                    context.chosen_locator,
                    commit_info,
                )
            elif self.kb_client:
                try:
                    self.kb_client.save_mapping(
                        page_url=getattr(context, "page_url", None),
                        broken_by=broken_by,
                        broken_value=broken_value,
                        healed_by=str(by_final),
                        healed_value=val_final,
                        source=context.source_of_chosen or "unknown",
                        score=float(raw_score or 0.0),
                    )
                except Exception:
                    pass

            context.final_status = "SUCCESS"
            logger.info(
                f"[HealingManager] PHỤC HỒI THÀNH CÔNG (fallback Python): {broken_value} -> {val_final}"
            )

        except Exception as e:
            context.final_status = "FAILURE"
            logger.error(
                f"[HealingManager] Pipeline TỰ PHỤC HỒI THẤT BẠI: {e}", exc_info=True
            )
            raise NoSuchElementException(f"Self-Healing Pipeline Failed: {e}")

        finally:
            context.end_timer()

            if self.persistence_service:
                try:
                    self.persistence_service.save_healing_event(context)
                except Exception as _e:
                    logger.error(
                        f"[HealingManager] Lỗi khi ghi PersistenceService: {_e}",
                        exc_info=True,
                    )
            else:
                logger.warning(
                    "[HealingManager] PersistenceService không khả dụng, bỏ qua ghi sự kiện heal."
                )

            logger.info(
                f"[HealingManager] Thời gian phục hồi fallback: {context.healing_duration_ms} ms"
            )

        return healed_element

    # ==================================================================
    # Helper: tạo hàm find_element có self-healing
    # ==================================================================
    def get_healing_find_function(self, driver) -> Callable:
        """
        find_element thông minh:

        TẦNG 1 (Native):
            - luôn thử driver.find_element() qua proxy trước
            - log rõ native success / native fail

        TẦNG 2 (Fallback Python):
            - chỉ chạy nếu native fail thật sự
            - có thể tắt bằng enable_python_fallback=False
            - hoặc ép native-only trong test_context
        """

        def _find_element_with_healing(
            driver,
            by: str,
            value: str,
            element_name: str,
            test_context: Optional[Dict[str, Any]] = None,
        ):
            if test_context is None:
                test_context = {}

            native_only = bool(test_context.get("native_only", False))

            try:
                el = driver.find_element(by, value)
                logger.info(
                    f"[HealingManager] (T1-native) FOUND: {element_name} "
                    f"(by={by}, value={value})"
                )
                return el

            except (NoSuchElementException, WebDriverException) as e:
                # ✅ Bắt cả WebDriverException vì Healenium proxy đôi khi wrap lỗi
                logger.warning(
                    f"[HealingManager] (T1-native) NOT FOUND/NOT HEALED: {element_name} "
                    f"(by={by}, value={value}). Exception={type(e).__name__}"
                )

                if native_only or not self.enable_python_fallback:
                    # ✅ Test native-only: không bật fallback thì fail thẳng
                    logger.error(
                        f"[HealingManager] Native-only mode: KHÔNG chạy fallback cho {element_name}."
                    )
                    raise NoSuchElementException(
                        f"Native Healenium failed for {element_name} (by={by}, value={value})"
                    )

                # TẦNG 2: Pipeline Python
                logger.warning(
                    f"[HealingManager] Kích hoạt pipeline fallback Python cho {element_name}..."
                )
                context = HealingContext(
                    driver=driver,
                    broken_locator=(by, value),
                    element_name=element_name,
                    test_context=test_context,
                )
                return self.heal(context)

        return partial(_find_element_with_healing, driver)

    # ==================================================================
    # Helper: wrapper chạy test có ghi log run_history
    # ==================================================================
    def run_test_wrapper(
        self,
        test_function: Callable,
        driver,
        test_id: str,
        wrapper=None,
        **kwargs,
    ):
        final_status = "Fail"
        run_id = None

        if self.persistence_service:
            run_id = self.persistence_service.save_raw_run_and_get_id(test_id)

        healing_find_func = self.get_healing_find_function(driver)

        try:
            test_function(
                driver=driver,
                healing_find_func=healing_find_func,
                test_id=test_id,
                run_id=run_id,
                **kwargs,
            )
            final_status = "Pass"

        except Exception as e:
            final_status = "Fail"
            logger.error(f"[HealingManager] Test case '{test_id}' thất bại: {e}")
            raise e

        finally:
            if run_id is not None and self.persistence_service:
                self.persistence_service.update_run_history_final_status(
                    run_id=run_id, final_status=final_status
                )
            elif run_id is None:
                logger.warning(
                    "[HealingManager] Không có 'run_id', không thể ghi lịch sử chạy cuối cùng."
                )

    def close(self):
        if self.persistence_service:
            self.persistence_service.close()
        if self.kb_client:
            pass
