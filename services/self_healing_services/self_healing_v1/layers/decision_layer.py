# self_healing_v1/layers/decision_layer.py

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

from selenium.webdriver.common.by import By

# Giữ nguyên import Fuzzy Model
try:
    from ..models.fuzzy_risk_model import risk_simulator
except ImportError:
    # Fallback nếu chưa cài scikit-fuzzy hoặc chưa có file model
    logging.warning("[DecisionLayer] Không tìm thấy fuzzy_risk_model. Sử dụng Mock Simulator.")
    class MockSimulator:
        input = {}
        output = {}
        def compute(self): self.output["risk_score"] = 0.5
    risk_simulator = MockSimulator()

from ..services.persistence_service import PersistenceService

logger = logging.getLogger(__name__)

class DecisionLayer:
    """
    DecisionLayer (Layer 3) - Fuzzy Logic Version
    Nhiệm vụ: Đánh giá rủi ro và ra quyết định chọn/bỏ locator.
    """

    def __init__(self, persistence_service: Optional[PersistenceService]):
        # Load Config
        try:
            CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "risk_model_config.json"
            self.config = self._load_config(CONFIG_PATH)
        except Exception:
            self.config = {}

        self.threshold_settings = self.config.get("threshold_settings", {})
        
        # Priority mapping
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
        logger.info(f"[DecisionLayer] Ready. Config loaded.")

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
    # 2. ADAPTER METHOD (Cầu nối cho HealingManager v1)
    # =========================================================
    def evaluate(self, similarity_score: float, stability_score: float = 0.5, context_match: float = 1.0) -> Dict[str, float]:
        """
        API chính được HealingManager gọi.
        Chuyển đổi tham số từ Manager -> Input cho Fuzzy Logic.
        """
        # 1. Chuẩn bị Input cho Fuzzy
        instability = 1.0 - stability_score
        failure_freq = instability  # Tạm thời coi tần suất lỗi tương đương độ mất ổn định
        priority_val = 0.5          # Default priority

        # 2. Gọi hàm tính toán nội bộ (để tận dụng logic Fuzzy)
        risk_score = self._compute_fuzzy_risk(priority_val, instability, failure_freq)

        # 3. Tính Threshold
        threshold = self._calculate_adaptive_threshold(risk_score)
        final_threshold = 0.0  # <--- Luôn chấp nhận mọi ứng viên

        return {
            "risk_score": round(risk_score, 2),
            "threshold": final_threshold 
        }

    # =========================================================
    # 3. RISK CALCULATION (FUZZY LOGIC INTERNAL)
    # =========================================================

    def _compute_fuzzy_risk(self, priority: float, instability: float, failure_freq: float) -> float:
        """Hàm nội bộ để chạy Simulator, dùng chung cho cả evaluate và _calculate_risk_score"""
        try:
            risk_simulator.input["priority"] = priority
            risk_simulator.input["instability"] = instability
            risk_simulator.input["failure_freq"] = failure_freq
            
            risk_simulator.compute()
            risk = self._clamp01(risk_simulator.output.get("risk_score", 0.5))
            
            # Log debug nhẹ
            # logger.debug(f"Fuzzy Input: P={priority}, I={instability}, F={failure_freq} -> Risk={risk}")
            return risk
        except Exception as e:
            logger.error(f"[DecisionLayer] Fuzzy Error: {e}. Default Risk=0.5")
            return 0.5

    def _calculate_metrics(self, test_history: List[Dict]) -> Tuple[float, float]:
        """Tính độ mất ổn định (Instability) và tần suất lỗi (Freq) từ lịch sử"""
        if not test_history:
            return 0.0, 0.0

        N = int(self.history_config.get("N", 100))
        M = int(self.history_config.get("M", 5))

        recent_n = test_history[-N:]
        recent_m = test_history[-M:]

        fails_n = sum(1 for r in recent_n if r.get("result") == "Fail" or r.get("status") == "Fail")
        fails_m = sum(1 for r in recent_m if r.get("result") == "Fail" or r.get("status") == "Fail")

        instability = fails_n / len(recent_n) if recent_n else 0.0
        freq = fails_m / len(recent_m) if recent_m else 0.0

        return self._clamp01(instability), self._clamp01(freq)

    def _calculate_risk_score(self, context: Dict[str, Any]) -> float:
        """
        [Legacy Support] Tính Risk Score dựa trên Context đầy đủ (dùng cho make_decision cũ).
        """
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

        # 3. Gọi hàm tính toán chung
        return self._compute_fuzzy_risk(priority_val, instability, failure_freq)

    def _calculate_adaptive_threshold(self, risk_score: float) -> float:
        """Risk càng cao -> Threshold càng khắt khe"""
        base = float(self.threshold_settings.get("base_threshold", 0.4))
        max_thresh = float(self.threshold_settings.get("max_threshold", 0.6))
        
        threshold = base + (max_thresh - base) * risk_score
        return self._clamp01(threshold)

    # =========================================================
    # 4. DECISION MAKING (CORE - LEGACY)
    # =========================================================

    def make_decision(
        self, 
        candidates: List[Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        
        logger.info("[DecisionLayer] Assessing candidates (Legacy Flow)...")
        context = context or {}

        # ... (Phần chuẩn hóa candidate giữ nguyên như code cũ của bạn) ...
        normalized_candidates = []
        for c in candidates:
            if isinstance(c, str):
                normalized_candidates.append({
                    "locator": c, "value": c, "score": 1.0, "source": "UNKNOWN"
                })
            elif isinstance(c, dict):
                normalized_candidates.append(c)
        candidates = normalized_candidates

        # 1. Tính toán
        risk_score = self._calculate_risk_score(context)
        threshold = self._calculate_adaptive_threshold(risk_score)

        default_result = {
            "chosen_locator": None, "source": None, "confidence": 0.0,
            "risk_score": risk_score, "adaptive_threshold": threshold, "status": "REJECTED"
        }

        if not candidates:
            return default_result

        # 2. Xử lý & Sắp xếp
        processed_candidates = []
        for c in candidates:
            raw_locator = c.get("locator") or c.get("value")
            score = self._clamp01(c.get("score", 0.0))
            source = c.get("source", "unknown")

            final_locator_tuple = None
            if isinstance(raw_locator, tuple):
                final_locator_tuple = raw_locator
            elif isinstance(raw_locator, str):
                clean_loc = raw_locator.strip()
                if clean_loc.startswith("/") or clean_loc.startswith("("):
                    final_locator_tuple = (By.XPATH, clean_loc)
                else:
                    final_locator_tuple = (By.CSS_SELECTOR, clean_loc)
            else:
                 # Fallback
                by_str = c.get("by", "xpath")
                val_str = c.get("value", "")
                if val_str:
                    final_locator_tuple = (self._resolve_by_string(by_str), val_str)

            if not final_locator_tuple: continue

            processed_candidates.append({
                "locator": final_locator_tuple,
                "score": score,
                "source": source,
                "priority": self.source_priority.get(source, 99)
            })

        if not processed_candidates: return default_result

        processed_candidates.sort(key=lambda x: (x['priority'], -x['score']))
        best_candidate = processed_candidates[0]
        best_score = best_candidate["score"]

        # 3. Ra quyết định
        status = "REJECTED"
        chosen_locator = None
        
        if best_score >= threshold:
            status = "ACCEPTED"
            chosen_locator = best_candidate["locator"]
        elif best_score >= (threshold - self.soft_margin):
            status = "SOFT_ACCEPT" 
            chosen_locator = best_candidate["locator"]

        return {
            "chosen_locator": chosen_locator,
            "source": best_candidate["source"],
            "confidence": best_score,
            "risk_score": risk_score,
            "adaptive_threshold": threshold,
            "status": status
        }

    def _resolve_by_string(self, by_str: str):
        mapping = {
            "id": By.ID, "xpath": By.XPATH, "name": By.NAME, 
            "class": By.CLASS_NAME, "css": By.CSS_SELECTOR,
            "css selector": By.CSS_SELECTOR, "link text": By.LINK_TEXT
        }
        return mapping.get(str(by_str).lower(), By.XPATH)

    # Alias
    decide = make_decision
