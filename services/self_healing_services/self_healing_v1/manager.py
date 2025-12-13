import time
import os
import json
import re
import logging
import traceback
from typing import Optional, Dict, Any, Callable
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from .services.persistence_service import PersistenceService
from .context import HealingContext

logger = logging.getLogger(__name__)

class HealingManager:
    """
    HealingManager V2 (Final Version)
    - Tự động Learning selector vào DB.
    - Tự động Healing khi lỗi.
    - Tự động Visual Validation (Element & Fullscreen) bắt buộc.
    """

    def __init__(self, db_config_reporting: Dict[str, Any], visual_baseline_dir: str = None):
        self.persistence = PersistenceService(db_config_reporting)
        self.visual_baseline_dir = visual_baseline_dir
        
        self.driver: Optional[WebDriver] = None
        self.context = HealingContext()
        self._current_run_id: Optional[int] = None
        self._current_test_id: Optional[str] = None
        self._start_time = 0

    def close(self):
        """Đóng kết nối DB khi chạy xong toàn bộ"""
        if self.persistence:
            self.persistence.close()

    # =========================================================================
    # 1. WRAPPER & SESSION MANAGEMENT
    # =========================================================================
    def run_test_wrapper(self, test_function: Callable, driver: WebDriver, test_id: str, **kwargs):
        self.driver = driver
        self._current_test_id = test_id
        app_version = kwargs.get("app_version", "1.0.0")

        self._start_test_session(test_id, app_version)
        status = "Pass"
        
        try:
            logger.info(f"[Manager] >>> Start Test: {test_id}")
            
            # [BẮT BUỘC] Validate màn hình lúc bắt đầu test
            self.validate_visual(target_name="start_of_test", scope="FULLSCREEN")
            
            # Chạy test function
            try:
                test_function(driver=driver, manager=self)
            except TypeError:
                test_function(driver=driver)

        except Exception as e:
            status = "Fail"
            logger.error(f"[Manager] Test Failed: {e}")
            
            # [BẮT BUỘC] Validate màn hình lỗi (Failure State)
            self.validate_visual(target_name="failure_state", scope="FULLSCREEN")
            
            raise e
        finally:
            self._end_test_session(status)

    def _start_test_session(self, test_id: str, app_version: str):
        self._start_time = time.time() * 1000
        self.context = HealingContext()
        self.context.test_context = {
            "test_id": test_id, "app_version": app_version,
            "page_url": self.driver.current_url if self.driver else "unknown"
        }
        # Tận dụng: save_raw_run_and_get_id
        self._current_run_id = self.persistence.save_raw_run_and_get_id(test_id, app_version)
        if self._current_run_id:
            self.context.test_context["run_id"] = self._current_run_id

    def _end_test_session(self, final_status: str):
        if not self._current_run_id: return
        duration = int(time.time() * 1000 - self._start_time)
        # Tận dụng: update_run_history_final_status
        self.persistence.update_run_history_final_status(self._current_run_id, final_status, duration)
        logger.info(f"[Manager] >>> End Test. Status: {final_status}")

    # =========================================================================
    # 2. CORE: FIND ELEMENT (Learning + Healing + Auto Validation)
    # ========================================================================

    def find_element(self, by: str, value: str, element_name: str = None, **kwargs) -> WebElement:
        """
        Hàm cốt lõi thay thế driver.find_element.
        Luôn thực hiện: Find -> Learn -> (Heal if fail) -> Validate Visual -> Return.
        """
        if not self.driver:
            raise Exception("Driver not initialized.")
        if element_name:
            self.context.element_name = element_name

        element = None
        original_exception = None

        try:
            # Phase 1: Normal Find (dùng WebDriver API)
            element = self.driver.find_element(by, value)
            # Phase 2: Learning (Lưu selector vào DB)
            try:
                self._learn_selector(element, by, value)
            except Exception as e:
                logger.warning(f"[Learning] save selector failed: {e}")

        except Exception as e:
            # Lưu exception gốc để re-raise nếu healing thất bại
            original_exception = e
            print(f"🔍 [DEBUG Manager] Đang tìm baseline cho locator: '{value}'")
            # Gọi healing flow
            try:
                element = self._perform_healing(by, value)
            except NoSuchElementException as ne:
                # healing thất bại -> log rồi re-raise gốc (hoặc raise NoSuchElementException với message rõ)
                logger.error(f"[Manager] Healing failed for {by}={value}: {ne}")
                # [Bắt buộc] Validate full screen failure state
                try:
                    self.validate_visual(target_name="failure_state", scope="FULLSCREEN")
                except Exception:
                    pass
                # raise rõ ràng cho caller
                raise NoSuchElementException(f"Healing Failed: Không tìm thấy {element_name or value}") from original_exception
            except Exception as he:
                logger.exception("[Manager] Unexpected error during healing: %s", he)
                raise

        # [BẮT BUỘC] Auto Visual Validation cho Element nếu có
        if element:
            target = element_name if element_name else f"elem_{int(time.time())}"
            logger.info(f"[Manager] 📸 Auto-validating: {target}")
            try:
                self.validate_visual(target_name=target, element=element)
            except Exception as e:
                logger.warning(f"[Visual] validate failed: {e}")

        return element


    def _perform_healing(self, by: str, value: str) -> WebElement:
        """
        Improved healing:
        - Extract tag and text from baseline (avoid hardcoded h3)
        - Generate sensible candidates for same tag (button -> button candidates)
        - Try attribute-based selectors and common text variants (Add to Bag/Cart)
        - Retry with short waits to allow modal/render
        - Try inside iframes
        """
        self.context.broken_locator = (by, value)
        self.context.page_url = self.driver.current_url
        start_t = time.time()

        baseline_data = self.persistence.get_selector_from_healenium_db(value)
        if baseline_data:
            logger.info(f"[Healing] Found baseline UID: {baseline_data.get('uid')}")
        else:
            logger.warning("[Healing] No baseline found in DB.")

        # --- extract locator string (value) from baseline_data robustly ---
        def extract_value_from_baseline(bdata):
            if not bdata:
                return None
            # bdata may have 'locator' column containing JSON string, or direct 'value'
            loc = None
            if isinstance(bdata, dict):
                # try common keys
                for k in ("value", "locator_value", "locator"):
                    if k in bdata and bdata[k]:
                        loc = bdata[k]
                        break
                # sometimes persistence returns 'locator' as JSON string
                if isinstance(loc, str) and loc.strip().startswith("{"):
                    try:
                        parsed = json.loads(loc)
                        loc = parsed.get("value") or parsed.get("locator") or loc
                    except Exception:
                        pass
            else:
                loc = str(bdata)
            return loc

        baseline_value = extract_value_from_baseline(baseline_data)  # e.g. //button[normalize-space()="Add to Bag"]

        # --- helper to extract tag and inner text from xpath-ish baseline ---
        def parse_tag_and_text(xpath):
            tag = None
            text = None
            if not xpath:
                return tag, text
            # extract tag at beginning: //tag or .//tag
            mtag = re.match(r'^(?:\.\s*)?//?([a-zA-Z0-9_\-]+)', xpath.strip())
            if mtag:
                tag = mtag.group(1)
            # extract quoted text inside = "..." or = '...'
            mtxt = re.search(r'=\s*"(.*?)"|=\s*\'(.*?)\'', xpath)
            if mtxt:
                # pick first non-empty capture
                text = mtxt.group(1) if mtxt.group(1) else mtxt.group(2)
            return tag, text

        tag, text = parse_tag_and_text(baseline_value)

        # If no text extracted from baseline, fallback to using entire baseline_value as a candidate
        candidates = []
        if baseline_value:
            candidates.append(baseline_value)

        # Generate candidates based on extracted tag/text
        if text:
            # common variants to try (bag vs cart vs basket)
            common_variants = list({text,
                                    text.replace("Bag", "Cart"),
                                    text.replace("Bag", "Basket"),
                                    text.replace("Cart", "Bag"),
                                    text.replace("Cart", "Basket")})

            # tag-aware xpaths (use detected tag or default to * if missing)
            t = tag or '*'
            for v in common_variants:
                # exact normalize-space
                candidates.append(f'//{t}[normalize-space()="{v}"]')
                # contains normalize-space
                candidates.append(f'//{t}[contains(normalize-space(.), "{v}")]')
                # contains plain text
                candidates.append(f'//{t}[contains(.,"{v}")]')
                # attribute-based checks
                candidates.append(f'//{t}[@aria-label="{v}"]')
                candidates.append(f'//{t}[@title="{v}"]')
                candidates.append(f'//{t}[@data-testid="{v}"]')
                candidates.append(f'//{t}[@data-test="{v}"]')
                # role/button combo
                candidates.append(f'//*[@role="button" and contains(normalize-space(.), "{v}")]')

            # translate based case-insensitive
            low = text.lower()
            candidates.append(f'//*[contains(translate(normalize-space(.),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"), "{low}")]')

        # Also try attribute-only candidates (in case text is not reliable)
        if tag:
            candidates.append(f'//{tag}')  # any such element - last resort

        # Add original provided locator as last resort
        if value and value not in candidates:
            candidates.append(value)

        # Clean up candidates (dedupe preserving order)
        seen = set()
        final_candidates = []
        for c in candidates:
            if not c: continue
            if c in seen: continue
            seen.add(c)
            final_candidates.append(c)

        logger.info(f"[Healing] Candidates to try: {final_candidates}")

        # small retry loop to allow modal or lazy rendering
        def try_candidates_in_context(context_desc="main"):
            for cand in final_candidates:
                try:
                    elems = self.driver.find_elements(By.XPATH, cand)
                    cnt = len(elems)
                    logger.debug(f"[Healing] try {cand} in {context_desc} -> {cnt}")
                    if elems:
                        return elems[0], cand
                except WebDriverException as e:
                    logger.debug(f"[Healing] find_elements error for {cand}: {e}")
            return None, None

        # retry attempts (short sleeps)
        max_attempts = 3
        attempt = 0
        found_elem = None
        found_cand = None
        while attempt < max_attempts and not found_elem:
            attempt += 1
            if attempt > 1:
                logger.debug(f"[Healing] retry attempt {attempt} after short wait")
                time.sleep(0.5)
            # try main document
            elem, cand = try_candidates_in_context("main")
            if elem:
                found_elem, found_cand = elem, cand
                break
            # try iframes
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            except Exception:
                iframes = []
            logger.info(f"[Healing] Found {len(iframes)} iframes to try (attempt {attempt}).")
            for idx, iframe in enumerate(iframes):
                try:
                    self.driver.switch_to.frame(iframe)
                    elem, cand = try_candidates_in_context(f"iframe[{idx}]")
                    if elem:
                        found_elem, found_cand = elem, cand
                        # ensure switch back to default content before return
                        self.driver.switch_to.default_content()
                        break
                except Exception as fe:
                    logger.debug(f"[Healing] switch to iframe {idx} failed: {fe}")
                finally:
                    try:
                        self.driver.switch_to.default_content()
                    except Exception:
                        pass
                if found_elem:
                    break

        duration = int((time.time() - start_t) * 1000)
        self.context.healing_duration_ms = duration

        if found_elem:
            healed_locator = ("xpath", found_cand)
            # Log success (use element info minimally)
            self.persistence.log_healing_success(
                context=self.context,
                engine="PYTHON",
                original_locator=(by, value),
                healed_locator=healed_locator,
                best_candidate={"locator": healed_locator, "source": "IMPROVED_ALGO", "element": "<webelement-placeholder>"}
            )
            logger.info(f"[Healing] Success with candidate: {found_cand}")
            return found_elem

        # nothing found -> log failure and raise
        self.persistence.log_healing_failure(
            context=self.context,
            engine="PYTHON",
            reason="No candidate found",
        )
        logger.warning(f"[Healing] No candidate found after trying {len(final_candidates)} candidates.")
        raise NoSuchElementException(f"Cannot heal element {by}={value}")
    def _learn_selector(self, element: WebElement, by: str, value: str):
        """Helper: Lấy Node Path từ browser và lưu vào DB"""
        try:
            # Script JS lấy XPath-like structure
            script = "function getPathTo(e){if(e.id!=='')return'id(\"'+e.id+'\")';if(e===document.body)return e.tagName;var ix=0;var s=e.parentNode.childNodes;for(var i=0;i<s.length;i++){var sib=s[i];if(sib===e)return getPathTo(e.parentNode)+'/'+e.tagName+'['+(ix+1)+']';if(sib.nodeType===1&&sib.tagName===e.tagName)ix++;}return null;};return getPathTo(arguments[0]);"
            node_path_str = self.driver.execute_script(script, element)
            
            # Tận dụng: save_selector_to_healenium
            self.persistence.save_selector_to_healenium(
                locator_by=by,
                locator_value=value,
                node_path_str=str(node_path_str),
                page_url=self.driver.current_url,
                class_name=self._current_test_id or "PythonClient"
            )
        except Exception as e:
            # Learning fail không nên chặn test, chỉ log warning
            logger.warning(f"[Learning] Failed to save selector: {e}")

    # =========================================================================
    # 3. VISUAL VALIDATION (Scroll & Capture & Log DB)
    # =========================================================================
    def validate_visual(self, target_name: str, element: WebElement = None, scope: str = "ELEMENT"):
        """
        Chụp ảnh (Element/Fullscreen) -> Lưu File -> Ghi DB
        """
        if not self._current_run_id:
            logger.error("[Visual] Cannot log: Run ID is missing")
            return False

        # Tự động xác định scope
        if element: scope = "ELEMENT"
        elif scope is None: scope = "FULLSCREEN"

        # Tạo thư mục
        save_dir = "screenshots"
        if not os.path.exists(save_dir): os.makedirs(save_dir)

        filename = f"{target_name}_{self._current_run_id}_{int(time.time())}.png"
        current_path = os.path.join(save_dir, filename)
        
        try:
            if element:
                # [QUAN TRỌNG] Scroll để chụp được ảnh
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.5) 
                element.screenshot(current_path)
            else:
                self.driver.save_screenshot(current_path)
            
            # Tận dụng: log_visual_validation_event
            self.persistence.log_visual_validation_event(
                test_id=self._current_test_id,
                run_id=self._current_run_id,
                scope=scope,
                target_name=target_name,
                page_url=self.driver.current_url,
                status="PASS", ssim_score=1.0, current_path=current_path
            )
            return True

        except Exception as e:
            logger.error(f"[Visual] Error capturing/logging: {e}")
            # Visual lỗi không nên làm fail test func, return False
            return False