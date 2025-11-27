# self_healing_v1/layers/validation_layer.py
import io
import re
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple, Union, Dict, Optional, Any

import numpy as np
from PIL import Image
from selenium.webdriver.remote.webelement import WebElement
from skimage.metrics import structural_similarity as ssim

import cv2  # dùng cho fullscreen validation

# NEW types (workflow mới)
from self_healing_v1.context import HealingContext, LocatorCandidate

logger = logging.getLogger(__name__)


class ValidationLayer:
    def __init__(
        self,
        baseline_dir: Union[Path, str] = "",
        threshold: float = 0.97,
        allow_autosize: bool = True,
        max_scale_delta: float = 0.10,
        per_element_thresholds: Dict[str, float] | None = None,
        soft_accept_margin: float = 0.02,  # margin cho SOFT_ACCEPT
    ):
        if not baseline_dir:
            self.baseline_dir = (
                Path(__file__).resolve().parent.parent / "visual_baseline"
            )
        else:
            self.baseline_dir = Path(baseline_dir)

        self.threshold = float(threshold)
        self.allow_autosize = bool(allow_autosize)
        self.max_scale_delta = float(max_scale_delta)
        self.per_element_thresholds = per_element_thresholds or {}
        self.soft_accept_margin = float(soft_accept_margin)

        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"[ValidationLayer] Khởi tạo. Baseline dir: {self.baseline_dir.resolve()}"
        )

        # FULLSCREEN baseline dir
        self.fullscreen_baseline_dir = self.baseline_dir / "fullscreen"
        self.fullscreen_baseline_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"[ValidationLayer] Fullscreen baseline dir: {self.fullscreen_baseline_dir.resolve()}"
        )

        # Lưu kết quả validate element gần nhất
        self._last_element_result: Optional[Dict[str, Any]] = None
        # Lưu kết quả fullscreen validate gần nhất
        self._last_fullscreen_result: Optional[Dict[str, Any]] = None

        # Cấu hình cho fullscreen validation
        self.full_min_good_matches = 20
        self.full_edge_diff_thr = 0.01  # tỉ lệ edge khác biệt tối đa để PASSED
        self.full_edge_soft_thr = 0.03  # DRIFT nếu dưới ngưỡng này

    # ---------- helpers (element-level) ----------
    @staticmethod
    def _safe_name(name: str) -> str:
        name = re.sub(r"[^0-9A-Za-z_\-]+", "_", name)
        return re.sub(r"_+", "_", name).strip("_")

    def _baseline_path(self, element_name: str) -> Path:
        return self.baseline_dir / f"{self._safe_name(element_name)}.png"

    def _fail_image_path(self, element_name: str) -> Path:
        return self.baseline_dir / f"{self._safe_name(element_name)}_FAILED.png"

    @staticmethod
    def _png_from_element(element: WebElement) -> bytes:
        return element.screenshot_as_png

    @staticmethod
    def _open_png(data: bytes) -> Image.Image:
        return Image.open(io.BytesIO(data)).convert("RGB")

    def _effective_threshold(self, element_name: str) -> float:
        base = float(
            self.per_element_thresholds.get(self._safe_name(element_name), self.threshold)
        )
        return min(max(base, 0.0), 1.0)

    def _compute_ssim(self, img1: Image.Image, img2: Image.Image) -> float:
        if img1.size != img2.size:
            if not self.allow_autosize:
                logger.warning("[ValidationLayer] ⚠ Kích thước ảnh khác nhau.")
                return 0.0

            w1, h1 = img1.size
            w2, h2 = img2.size
            sx = w2 / w1 if w1 else 1
            sy = h2 / h1 if h1 else 1

            if (
                abs(sx - 1) <= self.max_scale_delta
                and abs(sy - 1) <= self.max_scale_delta
            ):
                img1 = img1.resize((w2, h2), Image.BICUBIC)
            else:
                logger.warning(
                    "[ValidationLayer] ⚠ Chênh lệch kích thước vượt ngưỡng autosize."
                )
                return 0.0

        gray1 = np.array(img1.convert("L"))
        gray2 = np.array(img2.convert("L"))
        score, _ = ssim(gray1, gray2, full=True, data_range=255)
        return score

    def _save_diff_map(
        self, element_name: str, baseline_img: Image.Image, current_img: Image.Image
    ) -> Path | None:
        try:
            gray1 = np.array(baseline_img.convert("L"))
            gray2 = np.array(current_img.convert("L"))
            _, diff = ssim(gray1, gray2, full=True, data_range=255)
            diff_map = (1.0 - diff) * 255.0
            diff_img = Image.fromarray(diff_map.astype(np.uint8))
            path = self.baseline_dir / f"{self._safe_name(element_name)}_DIFF.png"
            diff_img.save(path, format="PNG")
            logger.info(f"[ValidationLayer] 🔎 Đã lưu diff map: {path.name}")
            return path
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi lưu diff map: {e}")
            return None

    def _log_diff_score(
        self,
        element_name: str,
        score: float,
        status: str = "NA",
        size: Tuple[int, int] | None = None,
    ):
        log_path = self.baseline_dir / "diff_log.csv"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_exists = log_path.exists()
        try:
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(
                        ["timestamp", "element_name", "ssim_score", "status", "width", "height"]
                    )
                w, h = (size or (None, None))
                writer.writerow(
                    [
                        timestamp,
                        self._safe_name(element_name),
                        f"{score:.5f}",
                        status,
                        w,
                        h,
                    ]
                )
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi khi ghi log CSV: {e}")

    # ---------- public (API cũ nhưng nâng cấp trả SOFT_ACCEPT + lưu result) ----------
    def validate_element(self, element: WebElement, element_name: str) -> str:
        """
        Trả về:
        "PASSED", "SOFT_ACCEPT", "FAILED", "NEW_BASELINE", "ERROR"

        Đồng thời self._last_element_result chứa:
          {
            "element_name": str,
            "status": str,
            "ssim_score": float | None,
            "baseline_path": str | None,
            "current_path": str | None,
            "diff_path": str | None,
          }
        """
        baseline_path = self._baseline_path(element_name)

        self._last_element_result = {
            "element_name": element_name,
            "status": "ERROR",
            "ssim_score": None,
            "baseline_path": None,
            "current_path": None,
            "diff_path": None,
        }

        try:
            current_png = self._png_from_element(element)
            current_img = self._open_png(current_png)
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi khi chụp ảnh '{element_name}': {e}")
            return "ERROR"

        # lưu current_path (luôn save để sau này upload)
        current_path = self.baseline_dir / f"{self._safe_name(element_name)}_CURRENT.png"
        try:
            with open(current_path, "wb") as f:
                f.write(current_png)
            self._last_element_result["current_path"] = str(current_path)
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi lưu current image '{current_path}': {e}")

        # (H09) Chưa có baseline -> tạo mới
        if not baseline_path.exists():
            try:
                with open(baseline_path, "wb") as f:
                    f.write(current_png)
                logger.info(
                    f"[ValidationLayer] (H09) 🟢 ĐÃ TẠO baseline: {baseline_path.name}"
                )
                self._log_diff_score(
                    element_name, 1.0, status="NEW_BASELINE", size=current_img.size
                )
                self._last_element_result.update(
                    {
                        "status": "NEW_BASELINE",
                        "ssim_score": 1.0,
                        "baseline_path": str(baseline_path),
                    }
                )
                return "NEW_BASELINE"
            except Exception as e:
                logger.error(f"[ValidationLayer] ❌ Lỗi lưu baseline '{baseline_path}': {e}")
                return "ERROR"

        # (H10) So sánh với baseline
        try:
            baseline_img = Image.open(baseline_path).convert("RGB")
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi đọc baseline '{baseline_path}': {e}")
            return "ERROR"

        self._last_element_result["baseline_path"] = str(baseline_path)

        # (H11) Tính SSIM
        score = self._compute_ssim(baseline_img, current_img)
        thr = self._effective_threshold(element_name)
        self._log_diff_score(
            element_name, score, status="EVALUATED", size=current_img.size
        )
        logger.info(
            f"[ValidationLayer] (H11) 🔍 SSIM = {score:.5f} (Ngưỡng: {thr})"
        )

        self._last_element_result["ssim_score"] = float(score)

        if score >= thr:
            logger.info("[ValidationLayer] ✔ PASSED: Khớp baseline.")
            self._last_element_result["status"] = "PASSED"
            return "PASSED"

        soft_thr = max(thr - self.soft_accept_margin, 0.0)
        if score >= soft_thr:
            logger.warning(
                f"[ValidationLayer] ◑ SOFT_ACCEPT: SSIM hơi dưới ngưỡng "
                f"(score={score:.5f}, thr={thr:.2f}, soft_thr={soft_thr:.2f})"
            )
            self._last_element_result["status"] = "SOFT_ACCEPT"
            return "SOFT_ACCEPT"

        # FAILED
        fail_path = self._fail_image_path(element_name)
        try:
            with open(fail_path, "wb") as f:
                f.write(current_png)
            diff_path = self._save_diff_map(element_name, baseline_img, current_img)
            logger.warning(
                f"[ValidationLayer] ✘ FAILED: Không khớp. Đã lưu ảnh lỗi: {fail_path.name}"
            )
            if diff_path is not None:
                self._last_element_result["diff_path"] = str(diff_path)
            self._last_element_result["status"] = "FAILED"
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi lưu ảnh lỗi '{fail_path}': {e}")

        return "FAILED"

    # ---------- Getter cho Manager/Persistence ----------
    def get_last_element_result(self) -> Optional[Dict[str, Any]]:
        return self._last_element_result

    # ---------- NEW: API cho workflow mới (fallback validate theo candidate) ----------
    def validate(self, context: HealingContext, candidate: LocatorCandidate) -> bool:
        """
        OK nếu PASSED / NEW_BASELINE / SOFT_ACCEPT.
        """
        driver = context.driver
        element_name = (
            context.element_name
            or f"{candidate['by']}_{self._safe_name(candidate['value'])}"
        )

        try:
            element = driver.find_element(candidate["by"], candidate["value"])
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Không thể tìm element để validate: {e}")
            status = "ERROR"
            ok = False
        else:
            status = self.validate_element(element, element_name)
            ok = status in ("PASSED", "NEW_BASELINE", "SOFT_ACCEPT")

        context.extra.setdefault("validation", {})
        context.extra["validation"].update(
            {
                "status": status,
                "element_name": element_name,
                "candidate_by": candidate["by"],
                "candidate_value": candidate["value"],
            }
        )
        return ok

    # ======================================================================
    # FULLSCREEN VALIDATION (OpenCV ORB + Edge diff)
    # ======================================================================
    def _fullscreen_baseline_path(self, page_name: str) -> Path:
        return self.fullscreen_baseline_dir / f"{self._safe_name(page_name)}.png"

    def _fullscreen_current_path(self, page_name: str) -> Path:
        return self.fullscreen_baseline_dir / f"{self._safe_name(page_name)}_CURRENT.png"

    def _fullscreen_diff_path(self, page_name: str) -> Path:
        return self.fullscreen_baseline_dir / f"{self._safe_name(page_name)}_DIFF.png"

    @staticmethod
    def _take_fullscreen_png(driver) -> bytes:
        return driver.get_screenshot_as_png()

    def validate_fullscreen(self, driver, page_name: str) -> str:
        """
        Validate fullscreen dùng:
          - ORB feature matching (good matches)
          - Edge-based diff (Canny)

        Trả về: "NEW_BASELINE", "PASSED", "DRIFT", "FAILED", "ERROR"
        """
        baseline_path = self._fullscreen_baseline_path(page_name)
        current_path = self._fullscreen_current_path(page_name)
        diff_path = self._fullscreen_diff_path(page_name)

        self._last_fullscreen_result = {
            "page_name": page_name,
            "status": "ERROR",
            "metrics": {},
            "baseline_path": None,
            "current_path": None,
            "diff_path": None,
        }

        # chụp fullscreen hiện tại
        try:
            png = self._take_fullscreen_png(driver)
            img = Image.open(io.BytesIO(png)).convert("RGB")
            img_np = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(
                f"[ValidationLayer] ❌ Lỗi chụp fullscreen '{page_name}': {e}",
                exc_info=True,
            )
            return "ERROR"

        # lưu current
        try:
            with open(current_path, "wb") as f:
                f.write(png)
            self._last_fullscreen_result["current_path"] = str(current_path)
        except Exception as e:
            logger.error(
                f"[ValidationLayer] ❌ Lỗi lưu fullscreen current '{current_path}': {e}"
            )

        # nếu chưa có baseline -> tạo baseline
        if not baseline_path.exists():
            try:
                with open(baseline_path, "wb") as f:
                    f.write(png)
                logger.info(
                    f"[ValidationLayer] 🟢 ĐÃ TẠO fullscreen baseline: {baseline_path.name}"
                )
                self._last_fullscreen_result.update(
                    {
                        "status": "NEW_BASELINE",
                        "baseline_path": str(baseline_path),
                        "metrics": {
                            "mode": "baseline_created",
                        },
                    }
                )
                return "NEW_BASELINE"
            except Exception as e:
                logger.error(
                    f"[ValidationLayer] ❌ Lỗi lưu fullscreen baseline '{baseline_path}': {e}"
                )
                return "ERROR"

        # đọc baseline
        try:
            baseline_png = baseline_path.read_bytes()
            baseline_img = Image.open(io.BytesIO(baseline_png)).convert("RGB")
            baseline_np = cv2.cvtColor(np.array(baseline_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            logger.error(
                f"[ValidationLayer] ❌ Lỗi đọc fullscreen baseline '{baseline_path}': {e}",
                exc_info=True,
            )
            return "ERROR"

        self._last_fullscreen_result["baseline_path"] = str(baseline_path)

        # ORB feature matching
        try:
            orb = cv2.ORB_create()
            kp1, des1 = orb.detectAndCompute(baseline_np, None)
            kp2, des2 = orb.detectAndCompute(img_np, None)

            if des1 is None or des2 is None:
                total_matches = 0
                good_matches = 0
            else:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)
                matches = sorted(matches, key=lambda x: x.distance)
                total_matches = len(matches)
                # ví dụ good_matches = distance < 50
                good_matches = len([m for m in matches if m.distance < 50])

            logger.info(
                f"[ValidationLayer] 🔍 Fullscreen matches: total={total_matches}, good={good_matches}"
            )
        except Exception as e:
            logger.error(
                f"[ValidationLayer] ❌ Lỗi ORB matching fullscreen '{page_name}': {e}",
                exc_info=True,
            )
            total_matches = 0
            good_matches = 0

        # Edge-based diff
        try:
            gray1 = cv2.cvtColor(baseline_np, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

            edges1 = cv2.Canny(gray1, 100, 200)
            edges2 = cv2.Canny(gray2, 100, 200)

            edge_diff = cv2.absdiff(edges1, edges2)
            non_zero = cv2.countNonZero(edge_diff)
            total_pixels = edge_diff.size
            edge_diff_ratio = non_zero / float(total_pixels) if total_pixels else 1.0

            logger.info(
                f"[ValidationLayer] 🔍 Fullscreen edge diff ratio = {edge_diff_ratio:.5f} "
                f"(non_zero={non_zero}, total={total_pixels})"
            )

            # lưu diff image
            try:
                color_diff = cv2.cvtColor(edge_diff, cv2.COLOR_GRAY2BGR)
                Image.fromarray(color_diff).save(diff_path)
                self._last_fullscreen_result["diff_path"] = str(diff_path)
            except Exception as e:
                logger.error(
                    f"[ValidationLayer] ❌ Lỗi lưu fullscreen diff '{diff_path}': {e}",
                    exc_info=True,
                )
        except Exception as e:
            logger.error(
                f"[ValidationLayer] ❌ Lỗi tính edge diff fullscreen '{page_name}': {e}",
                exc_info=True,
            )
            edge_diff_ratio = 1.0

        # quyết định status
        metrics = {
            "total_matches": int(total_matches),
            "good_matches": int(good_matches),
            "edge_diff_ratio": float(edge_diff_ratio),
        }

        status = "FAILED"
        if good_matches >= self.full_min_good_matches and edge_diff_ratio <= (
            self.full_edge_diff_thr
        ):
            status = "PASSED"
            logger.info(
                "[ValidationLayer] ✔ Fullscreen PASSED: gần như khớp layout."
            )
        elif edge_diff_ratio <= self.full_edge_soft_thr:
            status = "DRIFT"
            logger.warning(
                "[ValidationLayer] ◑ Fullscreen DRIFT: có thay đổi nhẹ nhưng được chấp nhận."
            )
        else:
            status = "FAILED"
            logger.warning(
                "[ValidationLayer] ✘ Fullscreen FAILED: layout thay đổi đáng kể."
            )

        self._last_fullscreen_result.update(
            {
                "status": status,
                "metrics": metrics,
            }
        )
        return status

    def get_last_fullscreen_result(self) -> Optional[Dict[str, Any]]:
        return self._last_fullscreen_result
