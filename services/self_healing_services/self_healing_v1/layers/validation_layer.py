# self_healing_v1/layers/validation_layer.py
import io, re, csv, logging
from pathlib import Path
from datetime import datetime
from typing import Tuple, Union, Dict

import numpy as np
from PIL import Image
from selenium.webdriver.remote.webelement import WebElement
from skimage.metrics import structural_similarity as ssim

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
        soft_accept_margin: float = 0.02,   # <<<< margin cho SOFT_ACCEPT
    ):
        if not baseline_dir:
            self.baseline_dir = Path(__file__).resolve().parent.parent / "visual_baseline"
        else:
            self.baseline_dir = Path(baseline_dir)

        self.threshold = float(threshold)
        self.allow_autosize = bool(allow_autosize)
        self.max_scale_delta = float(max_scale_delta)
        self.per_element_thresholds = per_element_thresholds or {}
        self.soft_accept_margin = float(soft_accept_margin)

        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[ValidationLayer] Khởi tạo. Baseline dir: {self.baseline_dir.resolve()}")

    # ---------- helpers ----------
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
        base = float(self.per_element_thresholds.get(self._safe_name(element_name), self.threshold))
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

            if abs(sx - 1) <= self.max_scale_delta and abs(sy - 1) <= self.max_scale_delta:
                img1 = img1.resize((w2, h2), Image.BICUBIC)
            else:
                logger.warning("[ValidationLayer] ⚠ Chênh lệch kích thước vượt ngưỡng autosize.")
                return 0.0

        gray1 = np.array(img1.convert("L"))
        gray2 = np.array(img2.convert("L"))
        score, _ = ssim(gray1, gray2, full=True, data_range=255)
        return score

    def _save_diff_map(self, element_name: str, baseline_img: Image.Image, current_img: Image.Image):
        try:
            gray1 = np.array(baseline_img.convert("L"))
            gray2 = np.array(current_img.convert("L"))
            _, diff = ssim(gray1, gray2, full=True, data_range=255)
            diff_map = (1.0 - diff) * 255.0
            diff_img = Image.fromarray(diff_map.astype(np.uint8))
            path = self.baseline_dir / f"{self._safe_name(element_name)}_DIFF.png"
            diff_img.save(path, format="PNG")
            logger.info(f"[ValidationLayer] 🔎 Đã lưu diff map: {path.name}")
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi lưu diff map: {e}")

    def _log_diff_score(self, element_name: str, score: float, status: str = "NA",
                        size: Tuple[int, int] | None = None):
        log_path = self.baseline_dir / "diff_log.csv"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_exists = log_path.exists()
        try:
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["timestamp", "element_name", "ssim_score", "status", "width", "height"])
                w, h = (size or (None, None))
                writer.writerow([timestamp, self._safe_name(element_name), f"{score:.5f}", status, w, h])
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi khi ghi log CSV: {e}")

    # ---------- public (API cũ nhưng nâng cấp trả SOFT_ACCEPT) ----------
    def validate_element(self, element: WebElement, element_name: str) -> str:
        """
        Trả về:
        "PASSED", "SOFT_ACCEPT", "FAILED", "NEW_BASELINE", "ERROR"
        """
        baseline_path = self._baseline_path(element_name)

        try:
            current_png = self._png_from_element(element)
            current_img = self._open_png(current_png)
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi khi chụp ảnh '{element_name}': {e}")
            return "ERROR"

        # (H09) Chưa có baseline -> tạo mới
        if not baseline_path.exists():
            try:
                with open(baseline_path, "wb") as f:
                    f.write(current_png)
                logger.info(f"[ValidationLayer] (H09) 🟢 ĐÃ TẠO baseline: {baseline_path.name}")
                self._log_diff_score(element_name, 1.0, status="NEW_BASELINE", size=current_img.size)
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

        # (H11) Tính SSIM
        score = self._compute_ssim(baseline_img, current_img)
        thr = self._effective_threshold(element_name)
        self._log_diff_score(element_name, score, status="EVALUATED", size=current_img.size)
        logger.info(f"[ValidationLayer] (H11) 🔍 SSIM = {score:.5f} (Ngưỡng: {thr})")

        if score >= thr:
            logger.info("[ValidationLayer] ✔ PASSED: Khớp baseline.")
            return "PASSED"

        soft_thr = max(thr - self.soft_accept_margin, 0.0)
        if score >= soft_thr:
            # <<<<< NÂNG CẤP: trả SOFT_ACCEPT thay vì PASSED
            logger.warning(
                f"[ValidationLayer] ◑ SOFT_ACCEPT: SSIM hơi dưới ngưỡng "
                f"(score={score:.5f}, thr={thr:.2f}, soft_thr={soft_thr:.2f})"
            )
            return "SOFT_ACCEPT"

        # FAILED
        fail_path = self._fail_image_path(element_name)
        try:
            with open(fail_path, "wb") as f:
                f.write(current_png)
            self._save_diff_map(element_name, baseline_img, current_img)
            logger.warning(f"[ValidationLayer] ✘ FAILED: Không khớp. Đã lưu ảnh lỗi: {fail_path.name}")
        except Exception as e:
            logger.error(f"[ValidationLayer] ❌ Lỗi lưu ảnh lỗi '{fail_path}': {e}")

        return "FAILED"

    # ---------- NEW: API cho workflow mới ----------
    def validate(self, context: HealingContext, candidate: LocatorCandidate) -> bool:
        """
        OK nếu PASSED / NEW_BASELINE / SOFT_ACCEPT.
        """
        driver = context.driver
        element_name = context.element_name or f"{candidate.by}_{self._safe_name(candidate.value)}"

        try:
            element = driver.find_element(candidate.by, candidate.value)
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
                "candidate_by": candidate.by,
                "candidate_value": candidate.value,
            }
        )
        return ok
