# self_healing_v1/layers/decision_layer.py

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

from selenium.webdriver.common.by import By

# Giả định mô hình fuzzy đã được định nghĩa đúng
from ..models.fuzzy_risk_model import risk_simulator
from ..services.persistence_service import PersistenceService

logger = logging.getLogger(__name__)

class DecisionLayer:
    """
    DecisionLayer (Layer 3)
    Nhiệm vụ: Đánh giá rủi ro và ra quyết định chọn/bỏ locator.
    
    Logic chính:
    1. Tính Risk Score (Dựa trên lịch sử test & priority).
    2. Tính Adaptive Threshold (Ngưỡng thích ứng).
    3. So sánh điểm của Candidate với Threshold để ra quyết định.
    """

    def __init__(self, persistence_service: Optional[PersistenceService]):
        # Load Config
        CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "risk_model_config.json"
        self.config = self._load_config(CONFIG_PATH)

        self.threshold_settings = self.config.get("threshold_settings", {})
        
        # Priority: Số càng nhỏ càng ưu tiên (VD: 1 > 2)
        # Suggestion (KB) thường ưu tiên hơn Heuristic
        self.source_priority = self.config.get("source_priority", {
            "healing_knowledge": 1, 
            "healing_layer_db": 2, 
            "healing_layer_heuristic": 3,
            "healing_layer_fallback": 4
        })
        
        self.history_config = {
            "N": self.config.get("history_length_n", 100),
            "M": self.config.get("history_length_m", 5),
        }

        self.priority_mapping = self.config.get("priority_mapping", {"default": 0.5})
        self.soft_margin = float(self.threshold_settings.get("soft_margin", 0.05))

        self.persistence_service = persistence_service
        logger.info(f"[DecisionLayer] Ready. Config loaded from {CONFIG_PATH}")

    # =========================================================
    # 1. HELPERS
    # =========================================================

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[DecisionLayer] Không tải được config ({e}). Dùng default.")
            return {}

    def _clamp01(self, x: float) -> float:
        return max(0.0, min(1.0, float(x)))

    # =========================================================
    # 2. RISK CALCULATION (FUZZY LOGIC)
    # =========================================================

    def _calculate_metrics(self, test_history: List[Dict]) -> Tuple[float, float]:
        """Tính độ mất ổn định (Instability) và tần suất lỗi (Freq)"""
        if not test_history:
            return 0.0, 0.0

        N = int(self.history_config.get("N", 100))
        M = int(self.history_config.get("M", 5))

        recent_n = test_history[-N:]
        recent_m = test_history[-M:]

        # Giả sử format history lưu: {'result': 'Pass'/'Fail', ...}
        fails_n = sum(1 for r in recent_n if r.get("result") == "Fail" or r.get("status") == "Fail")
        fails_m = sum(1 for r in recent_m if r.get("result") == "Fail" or r.get("status") == "Fail")

        instability = fails_n / len(recent_n) if recent_n else 0.0
        freq = fails_m / len(recent_m) if recent_m else 0.0

        return self._clamp01(instability), self._clamp01(freq)

    def _calculate_risk_score(self, context: Dict[str, Any]) -> float:
        """Sử dụng Fuzzy Logic để tính Risk Score"""
        
        # 1. Lấy Priority
        prio_str = str(context.get("test_case_priority", "default")).lower()
        priority_val = self.priority_mapping.get(prio_str, 0.5)

        # 2. Lấy History Metrics
        test_id = context.get("test_id")
        instability, failure_freq = 0.0, 0.0
        
        if test_id and self.persistence_service:
            try:
                history = self.persistence_service.load_history_for_test(test_id)
                instability, failure_freq = self._calculate_metrics(history)
            except Exception as e:
                logger.warning(f"[DecisionLayer] Lỗi load history: {e}")

        # 3. Chạy Fuzzy Simulation
        try:
            # Lưu ý: Simulation object thường không thread-safe.
            # Trong môi trường production parallel, cần tạo instance mới hoặc dùng Lock.
            # Ở đây giữ nguyên logic cũ của bạn.
            risk_simulator.input["priority"] = priority_val
            risk_simulator.input["instability"] = instability
            risk_simulator.input["failure_freq"] = failure_freq
            
            risk_simulator.compute()
            risk = self._clamp01(risk_simulator.output.get("risk_score", 0.5))
            
            logger.info(f"[DecisionLayer] Risk Calc: P={priority_val}, I={instability:.2f}, F={failure_freq:.2f} -> RISK={risk:.2f}")
            return risk
        except Exception as e:
            logger.error(f"[DecisionLayer] Fuzzy Error: {e}. Default Risk=0.5")
            return 0.5

    def _calculate_adaptive_threshold(self, risk_score: float) -> float:
        """Risk càng cao -> Threshold càng khắt khe"""
        base = float(self.threshold_settings.get("base_threshold", 0.6))
        max_thresh = float(self.threshold_settings.get("max_threshold", 0.9))
        
        # Công thức tuyến tính: Threshold = Base + (Range * Risk)
        threshold = base + (max_thresh - base) * risk_score
        return self._clamp01(threshold)

    # =========================================================
    # 3. DECISION MAKING (CORE)
    # =========================================================

    def make_decision(
        self, 
        candidates: List[Dict[str, Any]], 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        logger.info("[DecisionLayer] Assessing candidates...")
        context = context or {}

        # 1. Tính toán ngưỡng chấp nhận
        risk_score = self._calculate_risk_score(context)
        threshold = self._calculate_adaptive_threshold(risk_score)

        default_result = {
            "chosen_locator": None,
            "source": None,
            "confidence": 0.0,
            "risk_score": risk_score,
            "adaptive_threshold": threshold,
            "status": "REJECTED"
        }

        if not candidates:
            logger.info("[DecisionLayer] Không có candidate nào để đánh giá.")
            return default_result

        # 2. Chuẩn hóa & Sắp xếp Candidate
        # Layer 2 đã trả về Score chuẩn (0-1), ta chỉ việc dùng.
        processed_candidates = []
        for c in candidates:
            # Lấy thông tin locator. Hỗ trợ cả format cũ và mới
            raw_locator = c.get("locator") # Mong đợi: (By.ID, 'val')
            score = self._clamp01(c.get("score", 0.0))
            source = c.get("source", "unknown")

            # Nếu locator chưa ở dạng Tuple (By, value), cần parse (đề phòng)
            if not raw_locator:
                # Logic fallback cho code cũ
                by_str = c.get("by", "xpath")
                val_str = c.get("value", "")
                raw_locator = (self._resolve_by_string(by_str), val_str)

            processed_candidates.append({
                "locator": raw_locator,
                "score": score,
                "source": source,
                "priority": self.source_priority.get(source, 99)
            })

        # Sắp xếp: Ưu tiên Source (nhỏ tốt hơn) -> Sau đó đến Score (cao tốt hơn)
        processed_candidates.sort(key=lambda x: (x['priority'], -x['score']))

        best_candidate = processed_candidates[0]
        best_score = best_candidate["score"]
        
        logger.info(f"[DecisionLayer] Best Candidate: {best_candidate['locator']} (Score: {best_score:.2f} | Src: {best_candidate['source']})")

        # 3. Ra quyết định
        status = "REJECTED"
        chosen_locator = None
        
        # Logic so sánh ngưỡng
        if best_score >= threshold:
            status = "ACCEPTED"
            chosen_locator = best_candidate["locator"]
        elif best_score >= (threshold - self.soft_margin):
            # Vùng chấp nhận mềm (nếu cần cảnh báo nhưng vẫn cho chạy)
            status = "SOFT_ACCEPT" 
            chosen_locator = best_candidate["locator"]
            logger.warning(f"[DecisionLayer] Soft Accept: Score {best_score:.2f} gần đạt ngưỡng {threshold:.2f}")

        if status == "REJECTED":
            logger.warning(f"[DecisionLayer] Từ chối tất cả. Score cao nhất ({best_score:.2f}) < Threshold ({threshold:.2f})")

        return {
            "chosen_locator": chosen_locator,
            "source": best_candidate["source"],
            "confidence": best_score,
            "risk_score": risk_score,
            "adaptive_threshold": threshold,
            "status": status
        }

    def _resolve_by_string(self, by_str: str):
        """Helper map string sang Selenium By (cho trường hợp dữ liệu cũ)"""
        mapping = {
            "id": By.ID, "xpath": By.XPATH, "name": By.NAME, 
            "class": By.CLASS_NAME, "css": By.CSS_SELECTOR
        }
        return mapping.get(str(by_str).lower(), By.XPATH)

    # Alias
    decide = make_decision