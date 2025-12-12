# self_healing_v1/manager.py
import logging
from functools import partial
from typing import Any, Callable, Dict, Optional, Tuple
import time
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from .context import HealingContext
from .layers.suggestion_layer import SuggestionLayer
from .layers.healing_layer import HealingLayer
from .layers.decision_layer import DecisionLayer
from .layers.validation_layer import ValidationLayer
from .services.cloud_kb_client import CloudKnowledgeBaseClient
from .services.persistence_service import PersistenceService
from .utils.element_fingerprint import ElementFingerprint as FingerprintGenerator

logger = logging.getLogger(__name__)

DEFAULT_HEALENIUM_HOST = "http://localhost:7878"
HEALENIUM_WEBDRIVER_PATH = "/wd/hub"

class HealingManager:
    driver: Optional[RemoteWebDriver] = None
    _healenium_base_url: str = DEFAULT_HEALENIUM_HOST

    def __init__(
        self,
        db_config_kb: Dict[str, Any],
        db_config_reporting: Dict[str, Any],
        visual_baseline_dir: str = "visual_baseline",
        imitator_url: str = "http://localhost:8000",
        enable_python_fallback: bool = True,
        enable_native_element_validation: bool = True,
        healenium_host: Optional[str] = None,
    ):
        logger.info("Khởi tạo HealingManager...")

        self.healenium_host = healenium_host or DEFAULT_HEALENIUM_HOST
        HealingManager._healenium_base_url = self.healenium_host
        self.enable_python_fallback = enable_python_fallback
        self.enable_native_element_validation = enable_native_element_validation

        # KB + Suggestion Layer
        self.kb_client = None
        self.suggestion_layer = None
        try:
            self.kb_client = CloudKnowledgeBaseClient(db_config_kb)
            self.suggestion_layer = SuggestionLayer(self.kb_client)
            logger.info("[HealingManager] SuggestionLayer READY.")
        except Exception as e:
            logger.error("[HealingManager] ERROR Init SuggestionLayer", exc_info=True)

        # Persistence Service
        self.persistence_service = None
        try:
            self.persistence_service = PersistenceService(db_config_reporting)
            logger.info("[HealingManager] PersistenceService READY.")
        except Exception:
            logger.error("[HealingManager] ERROR Init PersistenceService", exc_info=True)

        # HealingLayer, DecisionLayer, ValidationLayer
        self.healing_layer = HealingLayer(driver=None, healenium_host=self.healenium_host)
        self.decision_layer = DecisionLayer(self.persistence_service)
        self.validation_layer = ValidationLayer(baseline_dir=visual_baseline_dir)

        logger.info("HealingManager READY (native + fallback)")

    # ==========================
    # Driver management
    # ==========================
    @classmethod
    def create_driver(cls, browser: str = "chrome") -> RemoteWebDriver:
        """
        Tạo WebDriver kết nối qua Healenium Proxy (hlm-proxy) để self-healing hoạt động.
        Nếu không kết nối được, sẽ fallback sang localhost.
        """
        options = Options()
        if browser.lower() != "chrome":
            raise ValueError("Only Chrome supported.")

        # Danh sách URL thử
        urls_to_try = [
            "http://hlm-proxy:8085/wd/hub",  # Docker network
            "http://localhost:7878/wd/hub"   # fallback host
        ]

        last_exception = None
        for url in urls_to_try:
            try:
                print(f"🔄 Connecting WebDriver → Healenium Proxy: {url}")
                cls.driver = webdriver.Remote(command_executor=url, options=options)
                # Kiểm tra kết nối
                cls.driver.execute_script("return navigator.userAgent;")
                print(f"✅ DRIVER READY via {url}")
                return cls.driver
            except WebDriverException as e:
                print(f"⚠ Cannot connect to {url}: {e}")
                last_exception = e
                time.sleep(1)  # delay nhỏ trước thử URL tiếp theo

        raise RuntimeError(f"❌ Cannot connect to any Healenium Proxy. Last error: {last_exception}")

    @classmethod
    def destroy_driver(cls):
        if cls.driver:
            cls.driver.quit()
            print("🔻 WebDriver closed.")
        cls.driver = None

    # ==========================
    # Fetch Healenium candidates
    # ==========================
    def fetch_healenium_candidates(self, broken_by: str, broken_value: str) -> list:
        try:
            url = f"{self.healenium_host}/healenium/selectors"
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')

            candidates = []
            for row in soup.select('table tbody tr'):
                cols = row.find_all('td')
                if len(cols) >= 5:
                    candidate_by = cols[0].text.strip()
                    candidate_value = cols[1].text.strip()
                    candidates.append({"by": candidate_by, "value": candidate_value, "source": "healenium"})
            return candidates
        except Exception as e:
            logger.warning(f"[HealingManager] Lỗi khi fetch Healenium selectors: {e}")
            return []

    # ==========================
    # Core self-healing pipeline
    # ==========================
    def heal(self, context: HealingContext) -> object:
        context.engine_used = "PYTHON"
        healed_element = None
        broken_by, broken_value = context.broken_locator

        # =================
        # 1) Healenium first
        # =================
        candidates = self.fetch_healenium_candidates(broken_by, broken_value)
        context.all_candidates = candidates

        for cand in candidates:
            try:
                el = context.driver.find_element(cand["by"], cand["value"])
                context.chosen_locator = (cand["by"], cand["value"])
                healed_element = el
                context.final_status = "SUCCESS"
                logger.info(f"[HealingManager] ✅ Healed via Healenium: {context.chosen_locator}")
                break
            except Exception:
                continue

        # =================
        # 2) Python fallback
        # =================
        if not healed_element:
            if not self.enable_python_fallback:
                raise NoSuchElementException(f"Element {broken_value} not found, fallback disabled")

            if context.driver is None:
                raise RuntimeError("Driver is None, cannot perform healing.")

            # Fingerprint for SuggestionLayer
            fingerprint_generator = FingerprintGenerator(context.broken_locator, context.driver)
            kb_candidates = []
            if self.suggestion_layer:
                kb_candidates = self.suggestion_layer.get_suggestions(context.broken_locator, context.driver) or []
                for cand in kb_candidates:
                    cand["source"] = "suggestion_kb"
                context.all_candidates.extend(kb_candidates)

            # HealingLayer
            if self.healing_layer:
                hl_candidates = self.healing_layer.get_candidates(context.driver, broken_by, broken_value) or []
                context.all_candidates.extend(hl_candidates)

            if not context.all_candidates:
                context.final_status = "FAILURE"
                raise NoSuchElementException("Self-Healing: Không tìm thấy ứng viên.")

            # DecisionLayer
            decision = self.decision_layer.make_decision(context.all_candidates, context.test_context)
            if decision.get("status") == "REJECTED":
                context.final_status = "FAILURE"
                raise NoSuchElementException("Self-Healing: DecisionLayer từ chối phục hồi.")

            by_final, val_final = decision["chosen_locator"]
            context.chosen_locator = (by_final, val_final)
            healed_element = context.driver.find_element(by_final, val_final)

        # =================
        # Validation Layer
        # =================
        if healed_element and self.validation_layer:
            try:
                visual_status = self.validation_layer.validate_element(healed_element, context.element_name)
                context.visual_validation_status = visual_status
            except Exception as ve:
                logger.error(f"[HealingManager] Lỗi validate element: {ve}", exc_info=True)

        # =================
        # Persistence
        # =================
        if self.persistence_service:
            try:
                self.persistence_service.save_healing_event(context)
            except Exception as e:
                logger.error(f"[HealingManager] Lỗi ghi heal event: {e}", exc_info=True)

        return healed_element

    # ==========================
    # Wrapper find_element thông minh
    # ==========================
    def get_healing_find_function(self, driver) -> Callable:
        def _find_element_with_healing(driver, by, value, element_name, test_context=None):
            if test_context is None:
                test_context = {}

            try:
                # Native find
                el = driver.find_element(by, value)
                logger.info(f"[HealingManager] (T1-native) FOUND: {element_name}")
                return el
            except Exception:
                # Healenium / fallback
                context = HealingContext(driver=driver, broken_locator=(by, value), element_name=element_name, test_context=test_context)
                return self.heal(context)

        return partial(_find_element_with_healing, driver)

    # ==========================
    # Fullscreen validation
    # ==========================
    def validate_fullscreen(self, driver, page_name: str, test_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if not self.validation_layer:
            return None
        try:
            status = self.validation_layer.validate_fullscreen(driver, page_name)
        except Exception as e:
            logger.error(f"Lỗi validate fullscreen: {e}")
            return None

        if self.persistence_service:
            detail = self.validation_layer.get_last_fullscreen_result() or {}
            metrics = detail.get("metrics") or {}
            self.persistence_service.log_visual_validation_event(
                test_id=(test_context or {}).get("test_id"),
                run_id=(test_context or {}).get("run_id"),
                scope="FULLSCREEN",
                target_name=page_name,
                page_url=(test_context or {}).get("page_url"),
                status=status,
                ssim_score=None,
                extra_metrics=metrics,
                baseline_path=detail.get("baseline_path"),
                current_path=detail.get("current_path"),
                diff_path=detail.get("diff_path"),
            )
        return status

    # ==========================
    # Test wrapper
    # ==========================
    def run_test_wrapper(self, test_function: Callable, *args, **kwargs):
        """Wrapper chạy test với healing + logging + persistence"""
        if not self.driver:
            self.create_driver()

        healing_find_func = self.get_healing_find_function(self.driver)
        kwargs.update({"healing_find_func": healing_find_func})

        run_context = {}
        if self.persistence_service:
            try:
                run_id = self.persistence_service.save_raw_run_and_get_id(test_function.__name__)
                run_context["run_id"] = run_id
                kwargs["run_id"] = run_id
            except Exception as e:
                logger.warning(f"PersistenceService chưa có method update_run_status, hãy dùng save_healing_event thay thế")
                kwargs["run_id"] = None

        try:
            result = test_function(*args, **kwargs)
            if self.persistence_service and run_context.get("run_id"):
                self.persistence_service.mark_run_success(run_context.get("run_id"))
            return result
        except Exception as e:
            logger.error(f"Test run FAILED: {e}", exc_info=True)
            if self.persistence_service and run_context.get("run_id"):
                self.persistence_service.mark_run_failed(run_context.get("run_id"))
            raise e

    # ==========================
    # Close resources
    # ==========================
    def close(self):
        if self.persistence_service:
            self.persistence_service.close()
        if self.kb_client and hasattr(self.kb_client, "close"):
            self.kb_client.close()
        if self.driver:
            self.destroy_driver()
