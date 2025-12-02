# self_healing_v1/manager.py
import logging
from functools import partial
from typing import Any, Callable, Dict, Optional
import time

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
        enable_python_fallback: bool = True,  # cho phép tắt fallback khi cần test native
        enable_native_element_validation: bool = True,  # validate element cho native/healenium
    ):
        logger.info("Khởi tạo HealingManager (workflow mới)...")

        self.healenium_host = healenium_host
        self.enable_python_fallback = enable_python_fallback
        self.enable_native_element_validation = enable_native_element_validation

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
        context.engine_used = "PYTHON"  # cho PersistenceService biết engine
        context.kb_candidates = getattr(context, "kb_candidates", []) or []
        context.hl_candidates = getattr(context, "hl_candidates", []) or []
        context.all_candidates = getattr(context, "all_candidates", []) or []

        healed_element = None

        try:
            broken_by, broken_value = context.broken_locator

            # đảm bảo có page_url nếu có thể
            try:
                if not getattr(context, "page_url", None) and context.driver:
                    context.page_url = context.driver.current_url
            except Exception:
                pass

            # 1) SuggestionLayer (từ KB)
            if self.suggestion_layer:
                kb_candidates = (
                    self.suggestion_layer.get_suggestions(
                        context.broken_locator, context.driver
                    )
                    or []
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
                    )
                    or []
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

            # 6) ValidationLayer (element-level cho fallback)
            if self.validation_layer:
                try:
                    visual_status = self.validation_layer.validate_element(
                        context.healed_element, context.element_name
                    )
                    context.visual_validation_status = visual_status
                    context.validation_scope = "ELEMENT"

                    # lấy SSIM score từ ValidationLayer lưu vào context -> heal_event
                    last_ele = self.validation_layer.get_last_element_result() or {}
                    context.last_ssim_score = last_ele.get("ssim_score")

                    if visual_status == "FAILED":
                        logger.warning(
                            f"[HealingManager] (H11) FAILED: '{context.element_name}' không khớp baseline."
                        )
                    elif visual_status == "SOFT_ACCEPT":
                        logger.warning(
                            f"[HealingManager] (H11) SOFT_ACCEPT: '{context.element_name}' hơi lệch baseline nhưng vẫn chấp nhận."
                        )

                    # log visual_validation_event vào DB (fallback)
                    if self.persistence_service:
                        tc = context.test_context or {}
                        test_id = tc.get("test_id")
                        run_id = tc.get("run_id")
                        page_url = getattr(context, "page_url", tc.get("page_url"))

                        self.persistence_service.log_visual_validation_event(
                            test_id=test_id,
                            run_id=run_id,
                            scope="ELEMENT",
                            target_name=context.element_name,
                            page_url=page_url,
                            status=visual_status,
                            ssim_score=last_ele.get("ssim_score"),
                            extra_metrics=None,
                            baseline_path=last_ele.get("baseline_path"),
                            current_path=last_ele.get("current_path"),
                            diff_path=last_ele.get("diff_path"),
                        )

                except Exception as ve:
                    logger.error(
                        f"[HealingManager] Lỗi validate element (fallback): {ve}",
                        exc_info=True,
                    )

            # 7) report to KB (Python fallback học vào KB)
            commit_info = (context.test_context or {}).get("commit_info", {}) or {}

            if self.suggestion_layer:
                try:
                    self.suggestion_layer.report_successful_heal(
                        old_locator=context.broken_locator,
                        new_locator=context.chosen_locator,
                        commit_info=commit_info,
                        source="python_fallback",
                        score=float(raw_score or 1.0),
                        duration_ms=context.healing_duration_ms or None,
                        page_url=getattr(context, "page_url", None),
                    )
                except Exception as e:
                    logger.error(
                        f"[HealingManager] Lỗi khi report_successful_heal lên SuggestionLayer: {e}",
                        exc_info=True,
                    )

            elif self.kb_client:
                # fallback: lưu trực tiếp nếu không có SuggestionLayer
                try:
                    self.kb_client.save_mapping(
                        page_url=getattr(context, "page_url", None),
                        broken_by=broken_by,
                        broken_value=broken_value,
                        healed_by=str(by_final),
                        healed_value=val_final,
                        source=context.source_of_chosen or "python_fallback",
                        score=float(raw_score or 0.0),
                    )
                except Exception as e:
                    logger.error(
                        f"[HealingManager] Lỗi khi lưu mapping trực tiếp vào KB: {e}",
                        exc_info=True,
                    )

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
            # Kết thúc timer của HealingContext (healing_duration_ms)
            context.end_timer()

            # Map healing_duration_ms -> python_overhead_ms để ghi vào heal_event
            if getattr(context, "healing_duration_ms", None) is not None:
                context.python_overhead_ms = context.healing_duration_ms

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
            - có thể kèm element-level validation cho native

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
            # cho phép bật/tắt visual check cho element native qua test_context
            visual_check_element = bool(test_context.get("visual_check_element", True))
            # cho phép test mô phỏng native-heal và log vào DB
            native_heal_sim = bool(test_context.get("native_heal_sim", False))

            # ==========================
            # TẦNG 1 — Native / Healenium
            # ==========================
            native_start = time.perf_counter()
            try:
                el = driver.find_element(by, value)
                native_end = time.perf_counter()
                native_overhead_ms = int((native_end - native_start) * 1000)

                logger.info(
                    f"[HealingManager] (T1-native) FOUND: {element_name} "
                    f"(native_overhead_ms={native_overhead_ms}, by={by}, value={value})"
                )

                # Element-level validation cho native / Healenium
                if (
                    self.validation_layer
                    and self.enable_native_element_validation
                    and visual_check_element
                ):
                    try:
                        visual_status = self.validation_layer.validate_element(
                            el, element_name
                        )
                        logger.info(
                            f"[HealingManager] (V-native) Visual status '{element_name}': {visual_status}"
                        )

                        # log visual event vào DB (native)
                        if self.persistence_service:
                            last_ele = (
                                self.validation_layer.get_last_element_result() or {}
                            )
                            test_id = test_context.get("test_id")
                            run_id = test_context.get("run_id")
                            page_url = test_context.get("page_url")

                            self.persistence_service.log_visual_validation_event(
                                test_id=test_id,
                                run_id=run_id,
                                scope="ELEMENT",
                                target_name=element_name,
                                page_url=page_url,
                                status=visual_status,
                                ssim_score=last_ele.get("ssim_score"),
                                extra_metrics=None,
                                baseline_path=last_ele.get("baseline_path"),
                                current_path=last_ele.get("current_path"),
                                diff_path=last_ele.get("diff_path"),
                            )

                    except Exception as ve:
                        logger.error(
                            f"[HealingManager] Lỗi validate element (native): {ve}",
                            exc_info=True,
                        )

                # 🔥 Nếu là test mô phỏng native-heal -> log heal_event engine='NATIVE'
                if native_heal_sim and self.persistence_service:
                    try:
                        ctx = HealingContext(
                            driver=driver,
                            broken_locator=(by, value),
                            element_name=element_name,
                            test_context=test_context,
                        )
                        ctx.engine_used = "NATIVE"
                        ctx.final_status = "SUCCESS"
                        ctx.broken_locator = (by, value)
                        ctx.chosen_locator = (by, value)

                        # page_url nếu có
                        try:
                            if not getattr(ctx, "page_url", None) and driver:
                                ctx.page_url = driver.current_url
                        except Exception:
                            pass

                        # gắn native_overhead_ms vào context để ghi DB
                        ctx.native_overhead_ms = native_overhead_ms

                        self.persistence_service.log_healing_success(
                            context=ctx,
                            engine="NATIVE",
                            original_locator=ctx.broken_locator,
                            healed_locator=ctx.chosen_locator,
                            best_candidate={"source": "healenium_native"},
                            basis_json={
                                "note": "Simulated native heal (native_heal_sim=True)"
                            },
                        )
                        logger.info(
                            "[HealingManager] (T1-native) ĐÃ LOG native heal vào DB (engine=NATIVE)."
                        )
                    except Exception as log_e:
                        logger.error(
                            f"[HealingManager] Lỗi khi log native heal (engine=NATIVE): {log_e}",
                            exc_info=True,
                        )

                return el

            except (NoSuchElementException, WebDriverException) as e:
                native_end = time.perf_counter()
                native_overhead_ms = int((native_end - native_start) * 1000)

                # Bắt cả WebDriverException vì Healenium proxy đôi khi wrap lỗi
                logger.warning(
                    f"[HealingManager] (T1-native) NOT FOUND/NOT HEALED: {element_name} "
                    f"(native_overhead_ms={native_overhead_ms}, by={by}, value={value}). "
                    f"Exception={type(e).__name__}"
                )

                if native_only or not self.enable_python_fallback:
                    # Test native-only: không bật fallback thì fail thẳng
                    logger.error(
                        f"[HealingManager] Native-only mode: KHÔNG chạy fallback cho {element_name}."
                    )
                    raise NoSuchElementException(
                        f"Native Healenium failed for {element_name} (by={by}, value={value})"
                    )

                # ==========================
                # TẦNG 2 — Pipeline Python
                # ==========================
                logger.warning(
                    f"[HealingManager] Kích hoạt pipeline fallback Python cho {element_name}..."
                )
                context = HealingContext(
                    driver=driver,
                    broken_locator=(by, value),
                    element_name=element_name,
                    test_context=test_context,
                )
                # gắn native_overhead_ms để ghi vào heal_event
                context.native_overhead_ms = native_overhead_ms

                return self.heal(context)

        return partial(_find_element_with_healing, driver)

    # ==================================================================
    # Helper: fullscreen validation (toàn trang)
    # ==================================================================
    def validate_fullscreen(
        self,
        driver,
        page_name: str,
        test_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Validate fullscreen (toàn trang) sử dụng OpenCV trong ValidationLayer.

        - driver: WebDriver hiện tại
        - page_name: tên logic của trang (dùng để map tới baseline image)
        - test_context: context thêm nếu cần log
        """
        if not self.validation_layer:
            logger.warning(
                "[HealingManager] ValidationLayer không khả dụng, bỏ qua fullscreen validation."
            )
            return None

        try:
            status = self.validation_layer.validate_fullscreen(driver, page_name)
        except Exception as e:
            logger.error(
                f"[HealingManager] Lỗi trong ValidationLayer.validate_fullscreen('{page_name}'): {e}",
                exc_info=True,
            )
            return None

        # log fullscreen visual vào DB
        if self.persistence_service and self.validation_layer:
            try:
                detail = self.validation_layer.get_last_fullscreen_result() or {}
                metrics = detail.get("metrics") or {}
                baseline_path = detail.get("baseline_path")
                current_path = detail.get("current_path")
                diff_path = detail.get("diff_path")

                tc = test_context or {}
                test_id = tc.get("test_id")
                run_id = tc.get("run_id")
                page_url = tc.get("page_url")

                self.persistence_service.log_visual_validation_event(
                    test_id=test_id,
                    run_id=run_id,
                    scope="FULLSCREEN",
                    target_name=page_name,
                    page_url=page_url,
                    status=status,
                    ssim_score=None,  # fullscreen không dùng SSIM, dùng metrics riêng
                    extra_metrics=metrics,
                    baseline_path=baseline_path,
                    current_path=current_path,
                    diff_path=diff_path,
                )
            except Exception as e:
                logger.error(
                    f"[HealingManager] Lỗi khi ghi fullscreen event vào PersistenceService: {e}",
                    exc_info=True,
                )

        return status

    # ==================================================================
    # Helper: wrapper chạy test có ghi log run_history
    # ==================================================================
    def run_test_wrapper(
        self,
        test_function: Callable,
        driver,
        test_id: str,
        wrapper=None,
        fullscreen_page_name: Optional[str] = None,  # cho phép truyền tên trang fullscreen
        **kwargs,
    ):
        final_status = "Fail"
        run_id = None

        # Đo thời gian bắt đầu test
        start_ts = time.perf_counter()

        if self.persistence_service:
            app_version = kwargs.get("app_version")
            run_id = self.persistence_service.save_raw_run_and_get_id(
                test_id, app_version=app_version
            )

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

            # Sau khi test pass, có thể chạy fullscreen validation nếu được cấu hình
            if fullscreen_page_name:
                try:
                    status = self.validate_fullscreen(
                        driver=driver,
                        page_name=fullscreen_page_name,
                        test_context={"test_id": test_id, "run_id": run_id},
                    )
                    logger.info(
                        f"[HealingManager] Fullscreen validation '{fullscreen_page_name}' => {status}"
                    )
                except Exception as ve:
                    logger.error(
                        f"[HealingManager] Lỗi khi validate fullscreen trong run_test_wrapper: {ve}",
                        exc_info=True,
                    )

        except Exception as e:
            final_status = "Fail"
            logger.error(f"[HealingManager] Test case '{test_id}' thất bại: {e}")
            # giữ hành vi cũ: vẫn throw ra cho caller
            raise e

        finally:
            # Đo thời gian kết thúc và tính duration
            end_ts = time.perf_counter()
            duration_ms = int((end_ts - start_ts) * 1000)

            if run_id is not None and self.persistence_service:
                self.persistence_service.update_run_history_final_status(
                    run_id=run_id,
                    final_status=final_status,
                    total_duration_ms=duration_ms,
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
