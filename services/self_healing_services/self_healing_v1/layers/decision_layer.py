# self_healing_v1/layers/decision_layer.py

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

from selenium.webdriver.common.by import By

from ..models.fuzzy_risk_model import risk_simulator
from ..services.persistence_service import PersistenceService

logger = logging.getLogger(__name__)

_BY_MAP = {
    "id": By.ID,
    "xpath": By.XPATH,
    "name": By.NAME,
    "classname": By.CLASS_NAME,
    "class": By.CLASS_NAME,
    "css": By.CSS_SELECTOR,
    "cssselector": By.CSS_SELECTOR,
    "linktext": By.LINK_TEXT,
    "partiallinktext": By.PARTIAL_LINK_TEXT,
    "tagname": By.TAG_NAME,
    "tag": By.TAG_NAME,
}


def _clamp01(x: float) -> float:
    """Kẹp một giá trị trong khoảng [0.0, 1.0]."""
    try:
        x = float(x)
    except Exception:
        x = 0.0
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


class DecisionLayer:
    """
    DecisionLayer – tầng “đánh giá rủi ro & ra quyết định”.

    Input:
      - candidates: list các locator candidate (by, value, score, source)
      - context: test_context (chứa test_id, priority, run_id, ...)

    Output:
      - dict:
        {
          chosen_locator: (By.<X>, value),
          source,
          confidence,        # score đã normalize [0,1]
          risk_score,
          adaptive_threshold,
          status: ACCEPTED | SOFT_ACCEPT | REJECTED
        }
    """

    def __init__(self, persistence_service: Optional[PersistenceService]):
        CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "risk_model_config.json"
        self.config = self._load_config(CONFIG_PATH)

        self.threshold_settings = self.config.get("threshold_settings", {})
        self.source_priority = self.config.get("source_priority", {})
        self.history_config = {
            "N": self.config.get("history_length_n", 100),
            "M": self.config.get("history_length_m", 5),
        }

        self.priority_mapping = self.config.get("priority_mapping", {}) or {}
        if "default" not in self.priority_mapping:
            self.priority_mapping["default"] = 0.5

        try:
            self.soft_margin = float(self.threshold_settings.get("soft_margin", 0.03))
        except Exception:
            self.soft_margin = 0.03

        self.persistence_service = persistence_service
        logger.info(f"[DecisionLayer] Đã khởi tạo và tải cấu hình từ: {CONFIG_PATH}")

    # =========================================================
    # CONFIG & HELPERS
    # =========================================================

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        logger.info(f"[DecisionLayer] Đang tải cấu hình từ: {config_path}")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"[Lỗi DecisionLayer] Không thể tải file config: {e}")
            return {}

    def _num(self, v: Any) -> float:
        try:
            return float(v)
        except Exception:
            return 0.0

    def _calculate_metrics(self, test_history: List[Dict]) -> Tuple[float, float]:
        """
        Tính:
          - instability: tỉ lệ raw_result='Fail' trong N lần chạy gần nhất.
          - failure_frequency: tỉ lệ raw_result='Fail' trong M lần gần nhất.
        """
        if not test_history:
            return 0.0, 0.0

        N = max(int(self.history_config.get("N", 100)), 1)
        M = max(int(self.history_config.get("M", 5)), 1)

        recent_n_runs = test_history[-N:]
        raw_failures_n = sum(1 for run in recent_n_runs if run.get("raw_result") == "Fail")
        instability = raw_failures_n / len(recent_n_runs) if recent_n_runs else 0.0

        recent_m_runs = test_history[-M:]
        raw_failures_m = sum(1 for run in recent_m_runs if run.get("raw_result") == "Fail")
        failure_frequency = raw_failures_m / len(recent_m_runs) if recent_m_runs else 0.0

        return _clamp01(instability), _clamp01(failure_frequency)

    def _map_priority_to_value(self, priority_tag: str) -> float:
        key = str(priority_tag).strip().lower()
        val = self.priority_mapping.get(key, self.priority_mapping["default"])
        return _clamp01(val)

    def _normalize_scores(self, candidates: List[Dict[str, Any]]) -> List[float]:
        """
        Chuẩn hóa score:
        - Nếu max_score <= 1: clamp 0..1
        - Nếu max_score > 1 (KB trả count): normalize theo max_score
        """
        raw_scores = [self._num(c.get("score", 0.0)) for c in candidates]
        max_raw = max(raw_scores) if raw_scores else 1.0

        if max_raw <= 1.0:
            return [_clamp01(s) for s in raw_scores]

        # normalize theo max_raw để giữ tương quan
        return [_clamp01(s / max_raw) for s in raw_scores]

    def _resolve_by(self, by_val: Union[str, By, Any]) -> Optional[By]:
        """
        Candidate by có thể là:
          - string: "xpath", "id", ...
          - enum By.XPATH, By.ID, ...
        """
        if isinstance(by_val, By):
            return by_val

        by_str = str(by_val or "").strip().lower()
        by_str = by_str.replace("_", "").replace(" ", "")
        return _BY_MAP.get(by_str)

    # =========================================================
    # (H06) Fuzzy Risk Score
    # =========================================================

    def _calculate_risk_score(self, context: Dict[str, Any]) -> float:
        logger.info("[H06] Đang tính toán Điểm Rủi ro bằng Fuzzy Logic (3-input)...")

        context = context or {}
        priority_string = context.get("test_case_priority", "default")
        priority_val = self._map_priority_to_value(priority_string)

        test_id = context.get("test_id")
        instability_val, failure_freq_val = 0.0, 0.0

        if not test_id:
            logger.warning("[H06] Không tìm thấy 'test_id'. Tính risk với instability=0, failure_freq=0.")
        elif not self.persistence_service:
            logger.warning("[H06] PersistenceService không khả dụng. Tính risk với instability=0, failure_freq=0.")
        else:
            try:
                test_history = self.persistence_service.load_history_for_test(test_id)
                if not isinstance(test_history, list):
                    test_history = []
                instability_val, failure_freq_val = self._calculate_metrics(test_history)
            except Exception as e:
                logger.error(
                    f"[H06] Lỗi khi tải lịch sử cho {test_id}: {e}. "
                    "Tính risk với instability=0, failure_freq=0."
                )

        logger.info(
            f"[H06] Inputs cho Fuzzy: Priority={priority_val:.2f}, "
            f"Instability={instability_val:.2%}, FailureFreq={failure_freq_val:.2%}"
        )

        try:
            risk_simulator.input["priority"] = priority_val
            risk_simulator.input["instability"] = instability_val
            risk_simulator.input["failure_freq"] = failure_freq_val
            risk_simulator.compute()

            risk_score = _clamp01(risk_simulator.output.get("risk_score", 0.5))
            logger.info(f"[H06] Điểm Rủi ro (Fuzzy): {risk_score:.2f}")
            return risk_score
        except Exception as e:
            logger.error(f"[H06] Lỗi khi tính toán Fuzzy: {e}. Trả về risk score mặc định (0.5).")
            return 0.5

    # =========================================================
    # (H07) Adaptive Threshold theo Risk
    # =========================================================

    def _calculate_adaptive_threshold(self, risk_score: float) -> float:
        base = float(self.threshold_settings.get("base_threshold", 0.80))
        max_thresh = float(self.threshold_settings.get("max_threshold", 0.95))

        base = min(max(base, 0.0), 1.0)
        max_thresh = min(max(max_thresh, base), 1.0)
        risk_score = _clamp01(risk_score)

        adaptive_threshold = base + (max_thresh - base) * risk_score
        logger.info(f"[H07] Ngưỡng Tin cậy Thích ứng: {adaptive_threshold:.2f}")
        return adaptive_threshold

    # =========================================================
    # (H08) Ra quyết định
    # =========================================================

    def make_decision(self, candidates: List[Dict[str, Any]], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info("[H08] Bắt đầu quá trình ra quyết định...")

        context = context or {}
        risk_score = self._calculate_risk_score(context)
        adaptive_threshold = self._calculate_adaptive_threshold(risk_score)

        result = {
            "chosen_locator": None,
            "source": None,
            "confidence": 0.0,
            "risk_score": risk_score,
            "adaptive_threshold": adaptive_threshold,
            "status": "REJECTED",
        }

        if not candidates:
            logger.warning("[H08] Quyết định: TỪ CHỐI (Không có ứng viên).")
            return result

        # normalize score list trước để sorting ổn định
        norm_scores = self._normalize_scores(candidates)
        for c, ns in zip(candidates, norm_scores):
            c["_score_norm"] = ns

        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                self.source_priority.get(c.get("source", "unknown"), 99),
                -self._num(c.get("_score_norm", c.get("score", 0.0))),
            ),
        )

        best = sorted_candidates[0]
        best_score_raw = self._num(best.get("score", 0.0))
        best_score_normalized = self._num(best.get("_score_norm", 0.0))

        logger.info(
            f"[H08] Ứng viên tốt nhất: {best} "
            f"(Điểm thô: {best_score_raw}, Đã chuẩn hóa: {best_score_normalized:.2f})"
        )

        by_enum = self._resolve_by(best.get("by"))
        value = best.get("value")

        if by_enum is None or not value:
            logger.error(f"[Lỗi H08] Ứng viên không hợp lệ (by='{best.get('by')}', value='{value}')")
            return result

        if best_score_normalized >= adaptive_threshold:
            status = "ACCEPTED"
            logger.info(f"[H08] ACCEPTED: {best_score_normalized:.2f} >= {adaptive_threshold:.2f}")
        elif best_score_normalized >= max(adaptive_threshold - self.soft_margin, 0.0):
            status = "SOFT_ACCEPT"
            logger.warning(
                f"[H08] SOFT_ACCEPT: {best_score_normalized:.2f} hơi dưới ngưỡng "
                f"{adaptive_threshold:.2f} (margin {self.soft_margin:.2f})"
            )
        else:
            logger.warning(f"[H08] REJECTED: {best_score_normalized:.2f} < {adaptive_threshold:.2f}")
            return result

        result.update(
            {
                "chosen_locator": (by_enum, value),
                "source": best.get("source"),
                "confidence": best_score_normalized,
                "status": status,
            }
        )
        return result

    # alias cho tương thích nếu chỗ nào gọi tên khác
    decide = make_decision
