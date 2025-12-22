import time
import json
import logging
import re
from datetime import datetime, timezone  # [SỬA] Thêm timezone
from typing import Optional, Dict, Any, Callable, List, Tuple
import difflib
        
from urllib.parse import urlparse

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

        # 1. Đồng bộ hóa Key 'dbname' để tránh lỗi chuyển đổi
        default_config = {
            "host": "localhost", "port": 5432, "dbname": "final",
            "user": "postgres", "password": "postgres",
        }
        
        db_config_reporting = db_config_reporting or default_config
        db_config_kb = db_config_kb or default_config

        self.driver: Optional[WebDriver] = None
        self.context = HealingContext()

        # 2. Khởi tạo Persistence Service
        self.persistence_service: Optional[PersistenceService] = None
        try:
            self.persistence_service = PersistenceService(db_config_reporting)
        except Exception as e:
            logger.error(f"[HealingManager] Persistence init failed: {e}")

        # 3. Khởi tạo KB System (Đoạn quan trọng nhất)
        self.kb_client: Optional[CloudKnowledgeBaseClient] = None
        self.suggestion_layer: Optional[SuggestionLayer] = None
        try:
            # Khởi tạo Client
            self.kb_client = CloudKnowledgeBaseClient(db_config_kb)
            
            # Chỉ khi Client thực sự Online mới khởi tạo Layer tiếp theo
            if self.kb_client and self.kb_client.enabled:
                self.suggestion_layer = SuggestionLayer(self.kb_client)
                logger.info("[HealingManager] KB System is fully ONLINE")
            else:
                logger.warning("[HealingManager] KB Client connected but is not ENABLED")
                
        except Exception as e:
            # Sửa đổi quan trọng: In ra lỗi thực tế (e) thay vì chỉ báo Offline chung chung
            logger.warning(f"[HealingManager] KB init failed (Offline Mode). Error: {e}")

        # 4. Khởi tạo các Layer còn lại
        self.healing_layer = HealingLayer() 
        if hasattr(self.healing_layer, "healenium_host"):
            self.healing_layer.healenium_host = healenium_host
        
        self.decision_layer = DecisionLayer(self.persistence_service)
        self.validation_layer = ValidationLayer(visual_baseline_dir)

        logger.info("[HealingManager] Ready")

    def _sanitize_selector(self, by: str, value: str) -> str:
        """Escape dấu hai chấm cho Tailwind CSS trong CSS Selector"""
        if (by == By.CSS_SELECTOR or by == "css selector") and ":" in value:
            # Nếu chưa có dấu escape (\:) thì mới thêm vào
            if "\\:" not in value:
                return value.replace(":", "\\:")
        return value
    
    def get_healing_find_function(self, driver: WebDriver) -> Callable:
        def wrapped_find(by: str, value: str, element_name: Optional[str] = None, **kwargs):
            if self.driver != driver:
                self.driver = driver
            return self.find_element(by, value, element_name, **kwargs)
        return wrapped_find

    def _learn_selector(self, element, by, value):
        """Hàm này chạy khi tìm thấy element thành công."""
        try:
            # 1. Kiểm tra xem element này có phải do Healenium tự sửa không?
            # Healenium thường đánh dấu phần tử đã sửa bằng thuộc tính 'hlm-id'
            is_healed = element.get_attribute("hlm-id")
            
            if is_healed and self.suggestion_layer:
                logger.info(f"[Manager] ⚡ Phát hiện Healenium đã sửa lỗi cho: {value}")
                
                # Lấy xpath hiện tại của phần tử đó để làm 'healed_locator'
                # Dùng script để lấy xpath chuẩn của phần tử vừa tìm được
                current_xpath = self.driver.execute_script(
                    "function getPath(e){if(e.id!=='')return 'id(\"'+e.id+'\")';if(e===document.body)return e.tagName;var x=0;var s=e.parentNode.childNodes;for(var i=0;i<s.length;i++){var t=s[i];if(t===e)return getPath(e.parentNode)+'/'+e.tagName+'['+(x+1)+']';if(t.nodeType===1&&t.tagName===e.tagName)x++}} return getPath(arguments[0]);", 
                    element
                )

                # 2. Lưu tri thức 'ké' từ Healenium vào hệ thống KB của Xuyn
                self.suggestion_layer.report_successful_heal(
                    broken_locator=(by, value),
                    healed_locator=("xpath", current_xpath),
                    page_url=self.driver.current_url,
                    score=1.0, # Healenium làm thì mình mặc định là 100% đúng
                    engine_name="healenium_sync"
                )
        except Exception:
            pass # Tránh làm gián đoạn luồng test chính
            
    def run_test_wrapper(
        self,
        test_function: Callable,
        driver: WebDriver,
        test_id: str,
        fullscreen_page_name: Optional[str] = None,
        **kwargs,
    ):
        self.driver = driver
        if hasattr(self.healing_layer, "driver"):
            self.healing_layer.driver = driver
        
        final_status = "FAIL"
        run_id = None
        
        # [SỬA 1] Lấy start time có múi giờ chuẩn
        start_ts = time.perf_counter()
        start_time_dt = datetime.now(timezone.utc)

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
                    self.persistence_service.finish_test_run(
                        run_id=run_id,
                        test_id=test_id,
                        start_time=start_time_dt, # [SỬA 2] Dùng biến đã tạo ở trên
                        final_status_from_runner=final_status
                    )
                except Exception:
                    logger.error("Failed to update run history", exc_info=True)

    def find_element(
        self,
        by: str,
        value: str,
        element_name: Optional[str] = None,
        timeout: int = 10,
        **kwargs,
    ) -> WebElement:
        if not self.driver:
            raise RuntimeError("Driver not initialized")

        if "test_context" in kwargs and hasattr(self.context, "test_context"):
            if isinstance(self.context.test_context, dict):
                self.context.test_context.update(kwargs["test_context"])
        
        self.context.reset_element_context(element_name)
        value = self._sanitize_selector(by, value)

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
        context.start_ts = time.perf_counter() # Bắt đầu đo thời gian
        context.driver = self.driver
        context.broken_locator = (by, value)
        
        # Sử dụng hasattr để kiểm tra hoặc gán thẳng nếu chưa có
        if not hasattr(context, 'project_id') or not context.project_id:
            try:
                from urllib.parse import urlparse
                context.project_id = urlparse(self.driver.current_url).netloc
            except Exception:
                context.project_id = "default_project"

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

        candidate_element = None
        
        # 0. Chuẩn bị Fingerprint & Context
        page_source = self.driver.page_source
        current_url = self.driver.current_url
        fingerprint = {}

        if self.suggestion_layer:
            # [SỬA 3] Gọi đúng hàm generate_fingerprint với 4 tham số
            fingerprint = self.suggestion_layer.generate_fingerprint(
                page_source=page_source, 
                locator_by=by, 
                locator_value=value, 
                page_url=current_url
            )
            context.fingerprint = fingerprint

        try:
            # LAYER 1: SUGGESTION
            if self.suggestion_layer:
                suggestion = self.suggestion_layer.find_suggestion(fingerprint, value)
                if suggestion:
                    # SỬA TẠI ĐÂY: Dùng ngoặc vuông ['...']
                    rate = suggestion.get('success_rate', 0) if isinstance(suggestion, dict) else suggestion['success_rate']
                    logger.info(f"[Healing] ✅ Found in KB (Success Rate: {rate}%)")
                    
                    try:
                        s_by = suggestion['new_locator_by']
                        s_val = suggestion['new_locator_value']
                        
                        s_val_clean = self._sanitize_selector(s_by, s_val)
                        by_type = By.XPATH if s_by.lower() == "xpath" else By.CSS_SELECTOR
                        
                        candidate_element = self.driver.find_element(by_type, s_val_clean)
                        
                        if candidate_element:
                            context.chosen_locator = (s_by, s_val_clean)
                            context.source_of_chosen = "KB"
                            context.raw_score = float(suggestion.get('last_score', 0.95))
                            logger.info(f"[Healing] ✅ KB Match Successful with: {s_val_clean}")
                    except Exception as e:
                        logger.warning(f"[Healing] KB element not present: {e}")
            # LAYER 2: LCS ANALYSIS
            if not candidate_element:
                logger.info("[Healing] 📉 KB missed. Starting LCS Analysis...")
                
                baseline_data = None
                if self.persistence_service:
                    try: 
                        # Lấy dữ liệu selector gốc từ database của Healenium để làm chuẩn (baseline)
                        baseline_data = self.persistence_service.get_selector_from_healenium_db(value)
                    except Exception as e:
                        logger.debug(f"Could not fetch baseline: {e}")
                
                def extract_loc(bdata):
                    if not bdata: return None
                    raw = bdata.get("locator") if isinstance(bdata, dict) else str(bdata)
                    clean = str(raw).strip() if raw else ""
                    if clean.startswith("{"):
                        try: return json.loads(clean).get("value")
                        except: pass
                    return clean
                    
                baseline_value = extract_loc(baseline_data) or value
                baseline_info = parse_baseline_info(baseline_value)

                # Thu hẹp phạm vi tìm kiếm để tăng hiệu năng
                search_tag = baseline_info["tag"]
                xpath_query = f"//{search_tag}" if (search_tag and search_tag != "*") else "//button | //a | //input | //div"
                
                try:
                    dom_elements = self.driver.find_elements(By.XPATH, xpath_query)
                except Exception:
                    dom_elements = []
                
                best_match = None
                highest_score = 0.0
                
                for elm in dom_elements:
                    try:
                        # Chỉ xét các phần tử đang hiển thị (tránh bẫy hidden elements)
                        if not elm.is_displayed(): continue
                        
                        curr_text = (elm.text or elm.get_attribute("innerText") or "").strip()
                        curr_id = (elm.get_attribute("id") or "").strip()
                        
                        # Tính điểm tương đồng dựa trên LCS
                        score_text = get_lcs_score(baseline_info["text"], curr_text)
                        score_id = get_lcs_score(baseline_info["id"], curr_id)
                        
                        # Trọng số ưu tiên Text (70%) vì ID thường bị thay đổi bởi framework
                        final_score = (score_text * 0.7) + (score_id * 0.3) if baseline_info["text"] else score_id
                        
                        if final_score > highest_score:
                            highest_score = final_score
                            best_match = elm
                    except: continue

                # Ngưỡng chấp nhận (Threshold) là 0.4
                if best_match and highest_score > 0.4:
                    candidate_element = best_match
                    try: 
                        tag = best_match.tag_name
                        text_val = best_match.text.strip()
                        
                        # [SỬA QUAN TRỌNG]: Xử lý dấu nháy đơn/kép trong text để tránh lỗi XPath syntax
                        if "'" in text_val:
                            gen_xpath = f"//{tag}[contains(., \"{text_val}\")]"
                        else:
                            gen_xpath = f"//{tag}[contains(., '{text_val}')]"
                            
                    except Exception: 
                        gen_xpath = "DOM_LCS_MATCH"
                        
                    context.chosen_locator = (By.XPATH, gen_xpath)
                    context.source_of_chosen = "LCS"
                    context.raw_score = highest_score
                    logger.info(f"[Healing] 🏆 LCS Winner: {gen_xpath} (Score: {highest_score:.2f})")
                else:
                    logger.warning(f"[Healing] LCS failed. Best score: {highest_score:.2f}")
                    
            # =========================================================
            # LAYER 3: DECISION (Fuzzy Logic & Adaptive Threshold)
            # =========================================================
            # Lấy Risk Score dựa trên Instability thực tế từ DB
            decision = self.decision_layer.evaluate(
                similarity_score=context.raw_score,
                locator_value=value,
                test_priority="high"
            )
            
            context.risk_score = decision['risk_score']
            context.adaptive_threshold = decision['threshold']
            
            logger.info(f"[Decision] Score: {context.raw_score:.2f} | Threshold: {context.adaptive_threshold:.2f} | Risk: {context.risk_score:.2f}")

            if context.raw_score < context.adaptive_threshold:
                raise NoSuchElementException(f"Bị từ chối bởi Fuzzy Logic. Score {context.raw_score} < Threshold {context.adaptive_threshold}")

            # Highlight
            self.driver.execute_script("arguments[0].style.border='3px solid red'", candidate_element)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", candidate_element)

            # LAYER 4: VALIDATION
            if self.validation_layer:
                try:
                    target_name = context.element_name if context.element_name else "healed_element_auto"
                    visual_status = self.validation_layer.validate_element_visual(candidate_element, target_name)
                    context.visual_validation_status = visual_status
                    
                    last_vis = self.validation_layer.get_last_element_result() or {}
                    ssim = last_vis.get("ssim_score", 0.0)
                    logger.info(f"[Validation] Status: {visual_status} | SSIM: {ssim:.4f}")
                except Exception as e:
                    logger.error(f"[Healing] Visual validation error: {e}", exc_info=True)
                    context.visual_validation_status = "ERROR"

            # =========================================================
            # 5. PERSISTENCE & LEARNING (GHI NHẬN KẾT QUẢ)
            # =========================================================
            context.final_status = "SUCCESS"
            
            # Tính toán thời gian sửa lỗi (ms)
            repair_time_ms = 0
            if hasattr(context, "start_ts") and context.start_ts:
                repair_time_ms = int((time.perf_counter() - context.start_ts) * 1000)

            if self.persistence_service:
                # A. Ghi sự kiện vào lịch sử Heal Event
                self.persistence_service._insert_heal_event(
                    context=context,
                    engine="PYTHON_V1",
                    success=True,
                    locator_old=value,
                    locator_new=context.chosen_locator[1] if context.chosen_locator else None,
                    chosen_source=context.source_of_chosen,
                    reason="Self-Healing Success",
                    basis_json=None
                )
                
                # B. Cập nhật độ mất ổn định (TĂNG SUCCESS) - Cơ sở cho Decision Layer
                self.persistence_service._update_locator_instability(
                    locator_old=value, 
                    success=True, 
                    project_id=context.project_id
                )
                
                # C. Ghi log Visual Validation nếu có
                if context.visual_validation_status != "N/A":
                    last_vis = self.validation_layer.get_last_element_result() or {}
                    self.persistence_service.log_visual_validation_event(
                        test_id=(context.test_context or {}).get("test_id"),
                        run_id=(context.test_context or {}).get("run_id"),
                        scope="ELEMENT", 
                        target_name=context.element_name or "healed_element",
                        page_url=current_url, 
                        status=context.visual_validation_status,
                        ssim_score=last_vis.get("ssim_score", 0.0),
                        baseline_path=last_vis.get("baseline_path"),
                        current_path=last_vis.get("current_path"),
                        diff_path=last_vis.get("diff_path")
                    )

            # D. Ghi vào Knowledge Base (Học tập cho lần sau - Layer 1)
            if self.suggestion_layer and context.chosen_locator:
                self.suggestion_layer.report_successful_heal(
                    broken_locator=(by, value),
                    healed_locator=context.chosen_locator,
                    page_url=current_url,
                    score=context.raw_score,
                    engine_name=context.source_of_chosen.lower(),
                    repair_time_ms=repair_time_ms
                )

        except Exception as e:
            # =========================================================
            # XỬ LÝ KHI HEALING THẤT BẠI
            # =========================================================
            context.final_status = "FAILURE"
            logger.error(f"[Healing] FAILED: {e}")
            
            if self.persistence_service:
                # A. Ghi sự kiện thất bại vào Heal Event
                self.persistence_service._insert_heal_event(
                    context=context,
                    engine="PYTHON_V1",
                    success=False,
                    locator_old=value,
                    locator_new=None,
                    chosen_source="NONE",
                    reason=str(e),
                    basis_json=None
                )
                # B. Cập nhật độ mất ổn định (TĂNG FAILURE) - Rất quan trọng để tăng Risk Score
                self.persistence_service._update_locator_instability(
                    locator_old=value, 
                    success=False, 
                    project_id=context.project_id
                )
            
            raise NoSuchElementException(f"Self-Healing failed: {e}")

        finally:
            context.end_timer()

        # TRẢ VỀ ELEMENT ĐỂ SELENIUM THỰC THI TIẾP
        return candidate_element
    def _report_event_to_db(self, context, old_val, success, reason=""):
        """Helper để gọi persistence_service lưu sự kiện."""
        self.persistence_service._insert_heal_event(
            context=context,
            engine="PYTHON_V1",
            success=success,
            locator_old=old_val,
            locator_new=context.chosen_locator[1] if context.chosen_locator else None,
            chosen_source=context.source_of_chosen,
            reason=reason if not success else "Success"
        )
    
    def validate_fullscreen(
        self,
        driver: WebDriver,
        page_name: str,
        test_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.validation_layer:
            return None

        status = self.validation_layer.validate_fullscreen(driver, page_name)
        full_result = self.validation_layer.get_last_fullscreen_result() or {}
        metrics = full_result.get("metrics", {})

        extra_data = {
            "good_matches": metrics.get("good_matches", 0),
            "edge_diff_ratio": metrics.get("edge_diff", 0.0),
            "total_matches": metrics.get("total_matches", 0)
        }

        if self.persistence_service:
            current_url = test_context.get("page_url") if test_context else driver.current_url
            
            self.persistence_service.log_visual_validation_event(
                test_id=test_context.get("test_id") if test_context else None,
                run_id=test_context.get("run_id") if test_context else None,
                scope="FULLSCREEN",
                target_name=page_name,
                page_url=current_url,
                status=status,
                ssim_score=0.0,
                extra_metrics=json.dumps(extra_data),
                baseline_path=full_result.get("baseline_path"),
                current_path=full_result.get("current_path"),
                diff_path=full_result.get("diff_path")
            )
        return status

    def close(self):
        if self.persistence_service:
            self.persistence_service.close()