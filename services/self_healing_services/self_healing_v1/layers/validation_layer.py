import io
import re
import logging
import numpy as np
import cv2
from pathlib import Path
from typing import Union, Dict, Optional, Any
from PIL import Image
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from skimage.metrics import structural_similarity as ssim

logger = logging.getLogger(__name__)

class ValidationLayer:
    def __init__(
        self,
        baseline_dir: Union[Path, str] = "",
        threshold: float = 0.95, 
        allow_autosize: bool = True,
        max_scale_delta: float = 0.15,
        per_element_thresholds: Optional[Dict[str, float]] = None,
        soft_accept_margin: float = 0.05,
    ):
        if not baseline_dir:
            self.baseline_dir = Path(__file__).resolve().parent.parent / "visual_baseline"
        else:
            self.baseline_dir = Path(baseline_dir)

        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.fullscreen_baseline_dir = self.baseline_dir / "fullscreen"
        self.fullscreen_baseline_dir.mkdir(parents=True, exist_ok=True)

        self.threshold = float(threshold)
        self.allow_autosize = bool(allow_autosize)
        self.per_element_thresholds = per_element_thresholds or {}
        self.soft_accept_margin = float(soft_accept_margin)
        
        # Config Fullscreen
        self.full_min_good_matches = 15
        self.full_edge_diff_thr = 0.02
        self.full_edge_soft_thr = 0.05

        # State storage - Đảm bảo cấu trúc đồng nhất
        self._last_element_result: Optional[Dict[str, Any]] = None
        self._last_fullscreen_result: Optional[Dict[str, Any]] = None
        
        logger.info(f"[ValidationLayer] Ready. Baseline: {self.baseline_dir}")

    # =========================================================
    # 1. ELEMENT VALIDATION
    # =========================================================

    def validate(
        self, 
        driver: WebDriver, 
        candidate: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        context = context or {}
        current_url = driver.current_url # Lấy URL ngay từ đầu
        
        locator = candidate.get("locator") or (candidate.get("by"), candidate.get("value"))
        element_name = context.get("element_name") or self._safe_name(str(locator[1]))
        
        # Khởi tạo result sớm để tránh lỗi NoneType khi Manager gọi lấy dữ liệu
        self._last_element_result = {
            "element_name": element_name,
            "url": current_url,
            "status": "ERROR",
            "ssim_score": 0.0,
            "baseline_path": None,
            "current_path": None,
            "diff_path": None
        }

        try:
            element = driver.find_element(*locator)
            if not self._validate_functional(element):
                self._last_element_result["status"] = "FUNC_FAILED"
                return False
            
            # Thực hiện visual check
            status = self.validate_element_visual(element, element_name)
            self._last_element_result["url"] = current_url # Đảm bảo URL luôn mới nhất
            
            return status in ("PASSED", "NEW_BASELINE", "SOFT_ACCEPT")

        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi validate element: {e}")
            self._last_element_result["status"] = "NOT_FOUND"
            return False

    def validate_element_visual(self, element: WebElement, element_name: str) -> str:
        baseline_path = self._baseline_path(element_name)
        current_path = self.baseline_dir / f"{element_name}_CURRENT.png"
        diff_path = self.baseline_dir / f"{element_name}_DIFF.png"
        
        try:
            current_png = element.screenshot_as_png
            current_img = Image.open(io.BytesIO(current_png)).convert("RGB")
            
            # Lưu ảnh hiện tại
            with open(current_path, "wb") as f:
                f.write(current_png)
            
            self._last_element_result.update({
                "current_path": str(current_path),
                "baseline_path": str(baseline_path)
            })

            # 1. Xử lý nếu chưa có baseline
            if not baseline_path.exists():
                with open(baseline_path, "wb") as f:
                    f.write(current_png)
                self._last_element_result.update({"status": "NEW_BASELINE", "ssim_score": 1.0})
                return "NEW_BASELINE"

            # 2. So sánh SSIM
            baseline_img = Image.open(baseline_path).convert("RGB")
            score = self._compute_ssim(baseline_img, current_img)
            effective_thr = self._effective_threshold(element_name)
            
            self._last_element_result["ssim_score"] = score
            
            if score >= effective_thr:
                status = "PASSED"
            elif score >= max(effective_thr - self.soft_accept_margin, 0.0):
                status = "SOFT_ACCEPT"
            else:
                status = "FAILED"
                self._save_diff_map(element_name, baseline_img, current_img)
                self._last_element_result["diff_path"] = str(diff_path)

            self._last_element_result["status"] = status
            return status

        except Exception as e:
            logger.error(f"[ValidationLayer] Visual Error: {e}")
            return "ERROR"

    # =========================================================
    # 2. FULLSCREEN VALIDATION
    # =========================================================

    def validate_fullscreen(self, driver: WebDriver, page_name: str) -> str:
        current_url = driver.current_url
        baseline_path = self._fullscreen_baseline_path(page_name)
        current_path = self._fullscreen_current_path(page_name)
        diff_path = self._fullscreen_diff_path(page_name)

        self._last_fullscreen_result = {
            "page_name": page_name,
            "url": current_url, # Thêm URL vào fullscreen
            "status": "ERROR",
            "metrics": {},
            "baseline_path": str(baseline_path),
            "current_path": str(current_path),
            "diff_path": None
        }

        try:
            png = driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(png)).convert("RGB")
            img_np = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            
            with open(current_path, "wb") as f:
                f.write(png)

            if not baseline_path.exists():
                with open(baseline_path, "wb") as f:
                    f.write(png)
                self._last_fullscreen_result["status"] = "NEW_BASELINE"
                return "NEW_BASELINE"

            baseline_img = Image.open(baseline_path).convert("RGB")
            baseline_np = cv2.cvtColor(np.array(baseline_img), cv2.COLOR_RGB2BGR)

            # Fix size mismatch
            if baseline_np.shape != img_np.shape:
                h, w = baseline_np.shape[:2]
                img_np = cv2.resize(img_np, (w, h))

            # Logic ORB & Edge Diff
            good_matches, total_matches = self._orb_compare(baseline_np, img_np)
            edge_diff_ratio = self._edge_compare(baseline_np, img_np, diff_path)
            
            # Decision
            status = "FAILED"
            if good_matches >= self.full_min_good_matches and edge_diff_ratio <= self.full_edge_diff_thr:
                status = "PASSED"
            elif edge_diff_ratio <= self.full_edge_soft_thr:
                status = "DRIFT"
            
            self._last_fullscreen_result.update({
                "status": status,
                "diff_path": str(diff_path) if status != "PASSED" else None,
                "metrics": {
                    "good_matches": good_matches,
                    "edge_diff": edge_diff_ratio,
                    "total_matches": total_matches
                }
            })
            return status

        except Exception as e:
            logger.error(f"[ValidationLayer] Fullscreen Error: {e}")
            return "ERROR"

    # =========================================================
    # HELPERS
    # =========================================================

    def _orb_compare(self, img1, img2):
        try:
            orb = cv2.ORB_create()
            kp1, des1 = orb.detectAndCompute(img1, None)
            kp2, des2 = orb.detectAndCompute(img2, None)
            if des1 is None or des2 is None: return 0, 0
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            good = [m for m in matches if m.distance < 50]
            return len(good), len(matches)
        except: return 0, 0

    def _edge_compare(self, img1, img2, diff_path):
        try:
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            edges1 = cv2.Canny(gray1, 100, 200)
            edges2 = cv2.Canny(gray2, 100, 200)
            diff = cv2.absdiff(edges1, edges2)
            
            color_diff = cv2.cvtColor(diff, cv2.COLOR_GRAY2BGR)
            cv2.imwrite(str(diff_path), color_diff)
            
            return cv2.countNonZero(diff) / float(diff.size)
        except: return 1.0

    def _validate_functional(self, element: WebElement) -> bool:
        try:
            return element.is_displayed() and element.size['width'] > 0
        except: return False

    def _compute_ssim(self, img1: Image.Image, img2: Image.Image) -> float:
        if img1.size != img2.size:
            img1 = img1.resize(img2.size, Image.BICUBIC)
        g1, g2 = np.array(img1.convert("L")), np.array(img2.convert("L"))
        score, _ = ssim(g1, g2, full=True, data_range=255)
        return float(score)

    def _save_diff_map(self, name, img1, img2):
        try:
            if img1.size != img2.size: img1 = img1.resize(img2.size, Image.BICUBIC)
            g1, g2 = np.array(img1.convert("L")), np.array(img2.convert("L"))
            _, diff = ssim(g1, g2, full=True, data_range=255)
            diff_img = Image.fromarray(((1.0-diff)*255).astype(np.uint8))
            diff_img.save(self.baseline_dir / f"{name}_DIFF.png")
        except: pass

    def _safe_name(self, n): return re.sub(r"[^0-9A-Za-z_\-]+", "_", n).strip("_")
    def _baseline_path(self, n): return self.baseline_dir / f"{self._safe_name(n)}.png"
    def _fullscreen_baseline_path(self, n): return self.fullscreen_baseline_dir / f"{self._safe_name(n)}.png"
    def _fullscreen_current_path(self, n): return self.fullscreen_baseline_dir / f"{self._safe_name(n)}_CURRENT.png"
    def _fullscreen_diff_path(self, n): return self.fullscreen_baseline_dir / f"{self._safe_name(n)}_DIFF.png"
    def _effective_threshold(self, n): return self.per_element_thresholds.get(self._safe_name(n), self.threshold)
    
    def get_last_element_result(self): return self._last_element_result
    def get_last_fullscreen_result(self): return self._last_fullscreen_result