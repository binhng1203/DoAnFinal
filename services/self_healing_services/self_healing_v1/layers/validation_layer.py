import io
import re
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple, Union, Dict, Optional, Any, List

import numpy as np
from PIL import Image
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from skimage.metrics import structural_similarity as ssim
import cv2 

# Cấu hình Logger
logger = logging.getLogger(__name__)

class ValidationLayer:
    """
    ValidationLayer (Layer 4) - Fixed Version
    """

    def __init__(
        self,
        baseline_dir: Union[Path, str] = "",
        threshold: float = 0.95, 
        allow_autosize: bool = True,
        max_scale_delta: float = 0.15,
        per_element_thresholds: Optional[Dict[str, float]] = None,
        soft_accept_margin: float = 0.05,
    ):
        # Setup đường dẫn thư mục ảnh
        if not baseline_dir:
            self.baseline_dir = Path(__file__).resolve().parent.parent / "visual_baseline"
        else:
            self.baseline_dir = Path(baseline_dir)

        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.fullscreen_baseline_dir = self.baseline_dir / "fullscreen"
        self.fullscreen_baseline_dir.mkdir(parents=True, exist_ok=True)

        # Config Validation Element
        self.threshold = float(threshold)
        self.allow_autosize = bool(allow_autosize)
        self.max_scale_delta = float(max_scale_delta)
        self.per_element_thresholds = per_element_thresholds or {}
        self.soft_accept_margin = float(soft_accept_margin)
        
        # Config Fullscreen (SỬA LỖI THIẾU ATTRIBUTE TẠI ĐÂY)
        self.full_min_good_matches = 15
        self.full_edge_diff_thr = 0.02
        self.full_edge_soft_thr = 0.05  # <--- Đã thêm biến này

        # State storage
        self._last_element_result: Optional[Dict[str, Any]] = None
        self._last_fullscreen_result: Optional[Dict[str, Any]] = None
        
        logger.info(f"[ValidationLayer] Ready. Baseline: {self.baseline_dir}")

    # =========================================================
    # 1. CORE API 
    # =========================================================

    def validate(
        self, 
        driver: WebDriver, 
        candidate: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        context = context or {}
        locator = candidate.get("locator")
        if not locator:
            locator = (candidate.get("by"), candidate.get("value"))

        element_name = context.get("element_name") or f"{self._safe_name(str(locator[1]))}"
        
        logger.info(f"[ValidationLayer] Bắt đầu validate candidate: {locator}")

        try:
            element = driver.find_element(*locator)
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Candidate không tìm thấy trên DOM: {e}")
            return False

        if not self._validate_functional(element):
            logger.warning(f"[ValidationLayer] ❌ Functional Check FAILED.")
            return False
        
        visual_status = self.validate_element_visual(element, element_name)
        
        if visual_status in ("PASSED", "NEW_BASELINE", "SOFT_ACCEPT"):
            logger.info(f"[ValidationLayer] ✔ Validation SUCCESS ({visual_status})")
            return True
        else:
            logger.warning(f"[ValidationLayer] ✘ Visual Validation FAILED ({visual_status})")
            return False

    # =========================================================
    # 2. FUNCTIONAL VALIDATION
    # =========================================================

    def _validate_functional(self, element: WebElement) -> bool:
        try:
            if not element.is_displayed():
                return False
            size = element.size
            if size['width'] <= 0 or size['height'] <= 0:
                return False
            # if not element.is_enabled(): return False
            return True
        except Exception as e:
            logger.error(f"[Validation] Lỗi khi check functional: {e}")
            return False

    # =========================================================
    # 3. VISUAL VALIDATION (Element Level)
    # =========================================================

    def validate_element_visual(self, element: WebElement, element_name: str) -> str:
        baseline_path = self._baseline_path(element_name)
        self._last_element_result = {
            "element_name": element_name, "status": "ERROR", "ssim_score": 0.0
        }

        try:
            current_png = element.screenshot_as_png
            current_img = Image.open(io.BytesIO(current_png)).convert("RGB")
            
            # Debug: Lưu ảnh hiện tại
            with open(self.baseline_dir / f"{element_name}_CURRENT.png", "wb") as f:
                f.write(current_png)
        except Exception as e:
            logger.error(f"[ValidationLayer] Không thể chụp ảnh element: {e}")
            return "ERROR"

        if not baseline_path.exists():
            try:
                with open(baseline_path, "wb") as f:
                    f.write(current_png)
                self._last_element_result.update({"status": "NEW_BASELINE", "ssim_score": 1.0})
                return "NEW_BASELINE"
            except Exception as e:
                logger.error(f"[ValidationLayer] Lỗi lưu baseline: {e}")
                return "ERROR"

        try:
            baseline_img = Image.open(baseline_path).convert("RGB")
            score = self._compute_ssim(baseline_img, current_img)
            
            effective_thr = self._effective_threshold(element_name)
            self._last_element_result["ssim_score"] = score
            
            logger.info(f"[ValidationLayer] SSIM Score: {score:.4f} (Threshold: {effective_thr})")

            if score >= effective_thr:
                self._last_element_result["status"] = "PASSED"
                return "PASSED"
            
            soft_thr = max(effective_thr - self.soft_accept_margin, 0.0)
            if score >= soft_thr:
                self._last_element_result["status"] = "SOFT_ACCEPT"
                return "SOFT_ACCEPT"

            self._save_diff_map(element_name, baseline_img, current_img)
            self._last_element_result["status"] = "FAILED"
            return "FAILED"

        except Exception as e:
            logger.error(f"[ValidationLayer] Lỗi so sánh ảnh: {e}")
            return "ERROR"

    # =========================================================
    # 4. FULLSCREEN VALIDATION (Fixed OpenCV Error)
    # =========================================================

    def _fullscreen_baseline_path(self, page_name: str) -> Path:
        return self.fullscreen_baseline_dir / f"{self._safe_name(page_name)}.png"

    def _fullscreen_current_path(self, page_name: str) -> Path:
        return self.fullscreen_baseline_dir / f"{self._safe_name(page_name)}_CURRENT.png"

    def _fullscreen_diff_path(self, page_name: str) -> Path:
        return self.fullscreen_baseline_dir / f"{self._safe_name(page_name)}_DIFF.png"

    def validate_fullscreen(self, driver, page_name: str) -> str:
        baseline_path = self._fullscreen_baseline_path(page_name)
        current_path = self._fullscreen_current_path(page_name)
        diff_path = self._fullscreen_diff_path(page_name)

        self._last_fullscreen_result = {
            "page_name": page_name, "status": "ERROR", "metrics": {},
            "baseline_path": None, "current_path": None, "diff_path": None
        }

        # 1. Chụp ảnh
        try:
            png = driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(png)).convert("RGB")
            img_np = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR) # Ảnh hiện tại
            
            # Lưu ảnh hiện tại
            with open(current_path, "wb") as f:
                f.write(png)
            self._last_fullscreen_result["current_path"] = str(current_path)
        except Exception as e:
            logger.error(f"[ValidationLayer] Lỗi chụp fullscreen: {e}")
            return "ERROR"

        # 2. Check Baseline
        if not baseline_path.exists():
            try:
                with open(baseline_path, "wb") as f:
                    f.write(png)
                logger.info(f"[ValidationLayer] 🟢 ĐÃ TẠO fullscreen baseline: {baseline_path.name}")
                return "NEW_BASELINE"
            except Exception:
                return "ERROR"

        # 3. Đọc Baseline
        try:
            baseline_png = baseline_path.read_bytes()
            baseline_img = Image.open(io.BytesIO(baseline_png)).convert("RGB")
            baseline_np = cv2.cvtColor(np.array(baseline_img), cv2.COLOR_RGB2BGR)
            self._last_fullscreen_result["baseline_path"] = str(baseline_path)
        except Exception:
            return "ERROR"

        # --- SỬA LỖI OPENCV SIZE MISMATCH TẠI ĐÂY ---
        # Kiểm tra nếu kích thước khác nhau thì resize ảnh hiện tại theo baseline
        if baseline_np.shape != img_np.shape:
            h, w = baseline_np.shape[:2]
            logger.warning(f"[ValidationLayer] Kích thước ảnh khác nhau (Baseline: {w}x{h} vs Current: {img_np.shape[1]}x{img_np.shape[0]}). Đang resize...")
            img_np = cv2.resize(img_np, (w, h))
        # ---------------------------------------------

        # 4. ORB Matching
        total_matches, good_matches = 0, 0
        try:
            orb = cv2.ORB_create()
            kp1, des1 = orb.detectAndCompute(baseline_np, None)
            kp2, des2 = orb.detectAndCompute(img_np, None)

            if des1 is not None and des2 is not None:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)
                total_matches = len(matches)
                good_matches = len([m for m in matches if m.distance < 50])
        except Exception as e:
            logger.error(f"[ValidationLayer] Lỗi ORB: {e}")

        # 5. Edge Diff
        edge_diff_ratio = 1.0
        try:
            gray1 = cv2.cvtColor(baseline_np, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

            edges1 = cv2.Canny(gray1, 100, 200)
            edges2 = cv2.Canny(gray2, 100, 200)

            # Bây giờ kích thước đã khớp, absdiff sẽ không lỗi
            edge_diff = cv2.absdiff(edges1, edges2)
            non_zero = cv2.countNonZero(edge_diff)
            total_pixels = edge_diff.size
            edge_diff_ratio = non_zero / float(total_pixels) if total_pixels else 1.0
            
            # Lưu diff image
            color_diff = cv2.cvtColor(edge_diff, cv2.COLOR_GRAY2BGR)
            Image.fromarray(color_diff).save(diff_path)
            self._last_fullscreen_result["diff_path"] = str(diff_path)

        except Exception as e:
            logger.error(f"[ValidationLayer] Lỗi Edge Diff: {e}")

        # 6. Status Decision
        status = "FAILED"
        if good_matches >= self.full_min_good_matches and edge_diff_ratio <= self.full_edge_diff_thr:
            status = "PASSED"
        elif edge_diff_ratio <= self.full_edge_soft_thr:
            status = "DRIFT"
        
        logger.info(f"[ValidationLayer] Fullscreen Result: {status} (Good Matches: {good_matches}, Edge Diff: {edge_diff_ratio:.5f})")
        return status

    # ... (Helpers giữ nguyên) ...
    def _compute_ssim(self, img1: Image.Image, img2: Image.Image) -> float:
        if img1.size != img2.size:
            if not self.allow_autosize: return 0.0
            img1 = img1.resize(img2.size, Image.BICUBIC)
        gray1 = np.array(img1.convert("L"))
        gray2 = np.array(img2.convert("L"))
        score, _ = ssim(gray1, gray2, full=True, data_range=255)
        return score

    def _save_diff_map(self, name, img1, img2):
        try:
            if img1.size != img2.size: img1 = img1.resize(img2.size, Image.BICUBIC)
            gray1, gray2 = np.array(img1.convert("L")), np.array(img2.convert("L"))
            _, diff = ssim(gray1, gray2, full=True, data_range=255)
            Image.fromarray(((1.0-diff)*255).astype(np.uint8)).save(self.baseline_dir / f"{name}_DIFF.png")
        except: pass

    def _safe_name(self, name): return re.sub(r"[^0-9A-Za-z_\-]+", "_", name).strip("_")
    def _baseline_path(self, name): return self.baseline_dir / f"{self._safe_name(name)}.png"
    def _effective_threshold(self, name): return self.per_element_thresholds.get(self._safe_name(name), self.threshold)
    def get_last_element_result(self): return self._last_element_result
    def get_last_fullscreen_result(self): return self._last_fullscreen_result