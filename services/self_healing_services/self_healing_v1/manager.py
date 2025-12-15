import time
import json
import logging
import re
from typing import Optional, Dict, Any, Callable, List, Tuple
import difflib
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

# Giả định các import này đã đúng với project structure của bạn
from .context import HealingContext
from .layers.suggestion_layer import SuggestionLayer
from .layers.healing_layer import HealingLayer
from .layers.decision_layer import DecisionLayer
from .layers.validation_layer import ValidationLayer
from .services.cloud_kb_client import CloudKnowledgeBaseClient
from .services.persistence_service import PersistenceService

logger = logging.getLogger(__name__)

class HealingManager:

    def __init__(
        self,
        db_config_reporting: Optional[Dict[str, Any]] = None,
        db_config_kb: Optional[Dict[str, Any]] = None,
        healenium_host: str = "http://localhost:7878",
        imitator_url: str = "http://localhost:8000",
        visual_baseline_dir: str = "visual_baseline",
    ):
        logger.info("[HealingManager] Initializing...")

        # 1. Xử lý Mutable Default Arguments
        if db_config_reporting is None:
            db_config_reporting = {
                "host": "localhost", "port": 5432, "database": "final",
                "user": "postgres", "password": "postgres",
            }
        if db_config_kb is None:
            db_config_kb = {
                "host": "localhost", "port": 5432, "database": "final",
                "user": "postgres", "password": "postgres",
            }

        self.driver: Optional[WebDriver] = None
        self.context = HealingContext()

        # 2. Setup Knowledge Base
        self.kb_client: Optional[CloudKnowledgeBaseClient] = None
        self.suggestion_layer: Optional[SuggestionLayer] = None
        try:
            self.kb_client = CloudKnowledgeBaseClient(db_config_kb)
            self.suggestion_layer = SuggestionLayer(self.kb_client)
        except Exception:
            logger.warning("[HealingManager] KB init failed or disabled (running in Offline Mode)")

        # 3. Setup Persistence Service
        self.persistence_service: Optional[PersistenceService] = None
        try:
            self.persistence_service = PersistenceService(db_config_reporting)
        except Exception:
            logger.error("[HealingManager] Persistence init failed", exc_info=True)

        # 4. Setup Core Layers
        self.healing_layer = HealingLayer() 
        if hasattr(self.healing_layer, "healenium_host"):
            self.healing_layer.healenium_host = healenium_host
        
        self.decision_layer = DecisionLayer(self.persistence_service)
        self.validation_layer = ValidationLayer(visual_baseline_dir)

        logger.info("[HealingManager] Ready")

    def get_healing_find_function(self, driver: WebDriver) -> Callable:
        def wrapped_find(by: str, value: str, element_name: Optional[str] = None, **kwargs):
            if self.driver != driver:
                self.driver = driver
            # SỬA: Truyền tiếp kwargs xuống find_element
            return self.find_element(by, value, element_name, **kwargs)
        return wrapped_find

    def _learn_selector(self, element: WebElement, by: str, value: str):
        pass

    def run_test_wrapper(
        self,
        test_function: Callable,
        driver: WebDriver,
        test_id: str,
        fullscreen_page_name: Optional[str] = None,
        **kwargs,
    ):
        self.driver = driver
        self.healing_layer.driver = driver
        
        final_status = "FAIL"
        run_id = None
        start_ts = time.perf_counter()

        if self.persistence_service:
            try:
                run_id = self.persistence_service.save_raw_run_and_get_id(
                    test_id, app_version=kwargs.get("app_version")
                )
                self.context.test_context = {"test_id": test_id, "run_id": run_id}
            except Exception as e:
                logger.error(f"Failed to create run entry: {e}")

        healing_find_func = self.get_healing_find_function(driver)

        try:
            test_function(
                driver=driver,
                healing_find_func=healing_find_func,
                test_id=test_id,
                run_id=run_id,
                **kwargs,
            )
            final_status = "PASS"

            # [POINT 1] Gọi hàm validate fullscreen đã được cập nhật logic
            if fullscreen_page_name:
                self.validate_fullscreen(
                    driver,
                    fullscreen_page_name,
                    {"test_id": test_id, "run_id": run_id, "page_url": driver.current_url},
                )

        except Exception:
            logger.error(f"[HealingManager] Test '{test_id}' FAILED", exc_info=True)
            raise

        finally:
            duration_ms = int((time.perf_counter() - start_ts) * 1000)
            if self.persistence_service and run_id:
                try:
                    self.persistence_service.update_run_history_final_status(
                        run_id, final_status, duration_ms,
                    )
                except Exception:
                    logger.error("Failed to update run history", exc_info=True)

    def find_element(
        self,
        by: str,
        value: str,
        element_name: Optional[str] = None,
        timeout: int = 10,
        **kwargs,  # SỬA: Thêm **kwargs để hứng test_context
    ) -> WebElement:
        if not self.driver:
            raise RuntimeError("Driver not initialized")

        # SỬA: Cập nhật Step Context (URL, Step Order, Action) vào HealingContext
        if "test_context" in kwargs:
            # Giả định HealingContext có phương thức update hoặc gán trực tiếp
            # Nếu class HealingContext của bạn dùng dict, hãy làm thế này:
            if hasattr(self.context, "test_context") and isinstance(self.context.test_context, dict):
                self.context.test_context.update(kwargs["test_context"])
        
        self.context.reset_element_context(element_name)

        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            self.context.raw_result = "PASS"
            self._learn_selector(element, by, value)
            return element

        except (TimeoutException, NoSuchElementException):
            logger.warning(f"[HealingManager] Native failed → Triggering Healing ({by}={value})")
            self.context.raw_result = "FAIL"
            return self._perform_healing(by, value)

    def _perform_healing(self, by: str, value: str) -> WebElement:
        context = self.context
        context.start_timer()
        context.driver = self.driver
        context.broken_locator = (by, value)
        
        def get_lcs_score(s1, s2):
            if not s1 or not s2: return 0.0
            return difflib.SequenceMatcher(None, str(s1), str(s2)).ratio()

        def parse_baseline_info(locator_str):
            info = {"tag": "*", "text": "", "id": "", "class": ""}
            if not locator_str: return info
            tag_match = re.search(r"//([a-zA-Z0-9]+)", locator_str)
            if tag_match: info["tag"] = tag_match.group(1)
            text_match = re.search(r"['\"]([^'\"]+)['\"]", locator_str)
            if text_match: info["text"] = text_match.group(1)
            id_match = re.search(r"@id=['\"]([^'\"]+)['\"]", locator_str)
            if id_match: info["id"] = id_match.group(1)
            return info

        try:
            # 1. Baseline from DB
            baseline_data = None
            if self.persistence_service:
                try: baseline_data = self.persistence_service.get_selector_from_healenium_db(value)
                except: pass
            
            def extract_loc(bdata):
                if not bdata: return None
                raw = bdata.get("locator") if isinstance(bdata, dict) else str(bdata)
                clean = str(raw).strip() if raw else ""
                if clean.startswith("{"):
                    try: return json.loads(clean).get("value")
                    except: pass
                return clean
                
            baseline_value = extract_loc(baseline_data) or value
            logger.info(f"[Healing] 🎯 Baseline Locator from DB: {baseline_value}")
            baseline_info = parse_baseline_info(baseline_value)

            # 2. Fast Candidates
            candidates = [baseline_value]
            final_candidates = list(dict.fromkeys(candidates))
            healed_element = None
            
            for cand in final_candidates:
                try:
                    strategy = By.XPATH if (cand.startswith("/") or cand.startswith("(")) else By.CSS_SELECTOR
                    elm = WebDriverWait(self.driver, 2).until(EC.presence_of_element_located((strategy, cand)))
                    if elm.is_displayed():
                        healed_element = elm
                        context.chosen_locator = (strategy, cand)
                        context.source_of_chosen = "DB_BASELINE"
                        context.raw_score = 1.0
                        break
                except: continue

            # 3. LCS Analysis
            if not healed_element:
                logger.info("[Healing] ⚠️ Fast heal failed. Starting LCS DOM Analysis...")
                search_tag = baseline_info["tag"]
                if search_tag == "*" or not search_tag: 
                    dom_elements = self.driver.find_elements(By.XPATH, "//button | //a | //input | //div[@role='button']")
                else:
                    dom_elements = self.driver.find_elements(By.TAG_NAME, search_tag)
                
                best_match = None
                highest_score = 0.0
                
                for elm in dom_elements:
                    try:
                        if not elm.is_displayed(): continue
                        curr_text = elm.text or elm.get_attribute("innerText") or elm.get_attribute("value") or ""
                        curr_id = elm.get_attribute("id") or ""
                        
                        score_text = get_lcs_score(baseline_info["text"], curr_text)
                        score_id = get_lcs_score(baseline_info["id"], curr_id)
                        
                        final_score = (score_text * 0.7) + (score_id * 0.3) if baseline_info["text"] else score_id
                        
                        if final_score > highest_score:
                            highest_score = final_score
                            best_match = elm
                    except: continue

                if best_match and highest_score > 0.5:
                    healed_element = best_match
                    self.driver.execute_script("arguments[0].style.border='3px solid red'", healed_element)
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", healed_element)
                    
                    try: gen_xpath = f"//{best_match.tag_name}[contains(text(), '{best_match.text}')]"
                    except: gen_xpath = "DOM_LCS_MATCH"
                        
                    context.chosen_locator = (By.XPATH, gen_xpath)
                    context.source_of_chosen = "LCS_ALGORITHM"
                    context.raw_score = highest_score
                    logger.info(f"[Healing] 🏆 LCS Winner: Score {highest_score:.2f} -> {gen_xpath}")
                else:
                    raise NoSuchElementException(f"LCS failed. Best score was {highest_score:.2f}")

            # 4. VISUAL VALIDATION
            if self.validation_layer and healed_element:
                try:
                    visual_status = self.validation_layer.validate_element_visual(healed_element, context.element_name)
                    context.visual_validation_status = visual_status
                except Exception:
                    logger.error("[Healing] Visual validation error", exc_info=True)

            # 5. REPORTING
            if self.persistence_service:
                self.persistence_service.log_healing_success(
                    context=context, engine="PYTHON", 
                    original_locator=(by, value), healed_locator=context.chosen_locator,
                    best_candidate={"locator": str(context.chosen_locator), "source": context.source_of_chosen, "score": context.raw_score}
                )
                
                # [POINT 2] Cập nhật phần log Visual Element để có diff_path và extra_metrics
                if context.visual_validation_status != "N/A":
                    last_vis = self.validation_layer.get_last_element_result() or {}
                    self.persistence_service.log_visual_validation_event(
                        test_id=(context.test_context or {}).get("test_id"),
                        run_id=(context.test_context or {}).get("run_id"),
                        scope="ELEMENT", 
                        target_name=context.element_name,
                        page_url=context.page_url, 
                        status=context.visual_validation_status,
                        ssim_score=last_vis.get("ssim_score"),
                        
                        # [SỬA] Thêm path và metrics rỗng
                        baseline_path=last_vis.get("baseline_path"),
                        current_path=last_vis.get("current_path"),
                        diff_path=last_vis.get("diff_path"), 
                        extra_metrics="{}" 
                    )

            if self.suggestion_layer:
                try:
                    self.suggestion_layer.report_successful_heal(
                        old_locator=context.broken_locator, new_locator=context.chosen_locator,
                        source="LCS", score=context.raw_score, page_url=context.page_url
                    )
                except: pass

            context.final_status = "SUCCESS"
            return healed_element

        except Exception as e:
            context.final_status = "FAILURE"
            logger.error(f"[Healing] FAILED: {e}")
            raise NoSuchElementException(f"Self-Healing failed: {e}")

        finally:
            context.end_timer()
            if self.persistence_service and context.final_status != "SUCCESS":
                try: self.persistence_service.save_healing_event(context)
                except: pass

    # ==========================================================
    # HÀM validate_fullscreen ĐÃ ĐƯỢC CẬP NHẬT HOÀN CHỈNH
    # ==========================================================
    def validate_fullscreen(
        self,
        driver: WebDriver,
        page_name: str,
        test_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.validation_layer:
            return None

        # 1. Gọi hàm validate từ ValidationLayer
        status = self.validation_layer.validate_fullscreen(driver, page_name)

        # 2. Lấy dữ liệu chi tiết
        full_result = self.validation_layer.get_last_fullscreen_result() or {}
        metrics = full_result.get("metrics", {})

        # 3. Chuẩn bị dữ liệu JSON metrics
        extra_data = {
            "good_matches": metrics.get("good_matches", 0),
            "edge_diff_ratio": metrics.get("edge_diff", 0.0),
            "total_matches": metrics.get("total_matches", 0)
        }

        # 4. Ghi xuống DB với đầy đủ tham số
        if self.persistence_service:
            # Xác định URL
            current_url = test_context.get("page_url") if test_context else driver.current_url
            
            self.persistence_service.log_visual_validation_event(
                test_id=test_context.get("test_id") if test_context else None,
                run_id=test_context.get("run_id") if test_context else None,
                scope="FULLSCREEN",
                target_name=page_name,
                page_url=current_url,
                
                status=status,
                ssim_score=0.0, # Fullscreen dùng edge diff
                
                # [QUAN TRỌNG] Chuyển metrics thành JSON string
                extra_metrics=json.dumps(extra_data),
                
                # [QUAN TRỌNG] Truyền đường dẫn file
                baseline_path=full_result.get("baseline_path"),
                current_path=full_result.get("current_path"),
                diff_path=full_result.get("diff_path")
            )
        return status

    def close(self):
        if self.persistence_service:
            self.persistence_service.close()