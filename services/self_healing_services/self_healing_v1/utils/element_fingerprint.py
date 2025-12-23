import logging
import hashlib
from typing import Tuple, Dict, Any, Optional
from selenium.webdriver.common.by import By
import re

logger = logging.getLogger(__name__)

class ElementFingerprint:
    """
    Tạo 'chữ ký' (fingerprint) cho Locator.
    Chữ ký này dùng để định danh locator hỏng và tra cứu trong KB.
    """

    def __init__(self, locator: Tuple[str, str]):
        # KHÔNG NHẬN DRIVER NỮA
        self.by = locator[0]
        self.value = locator[1]

    def get(self) -> Dict[str, Any]:
        """
        Trả về dictionary chứa thông tin fingerprint.
        """
        try:
            features = self._extract_features()
            # Tạo hash unique dựa trên features
            fingerprint_hash = self._generate_hash(features)
            
            return {
                "locator_hash": fingerprint_hash,
                "locator_by": self.by,
                "locator_value": self.value,
                "features": features
            }
        except Exception as e:
            logger.error(f"[Fingerprint] Lỗi tạo fingerprint: {e}")
            return {}

    def _extract_features(self) -> Dict[str, str]:
        """
        Phân tích chuỗi locator để lấy đặc điểm (Tag, ID, Text...).
        Chủ yếu hỗ trợ XPath và CSS.
        """
        features = {"tag": "*"}
        val = self.value
        
        # Regex đơn giản để bắt tag, id, text từ XPath
        if self.by == By.XPATH or self.by == "xpath":
            tag_match = re.search(r"//([\w\-]+)", val)
            if tag_match: features["tag"] = tag_match.group(1)
            
            id_match = re.search(r"@id=['\"](.*?)['\"]", val)
            if id_match: features["id"] = id_match.group(1)
            
            text_match = re.search(r"text\(\)\s*=\s*['\"](.*?)['\"]", val)
            if text_match: features["text"] = text_match.group(1)
            
        return features

    def _generate_hash(self, features: Dict[str, str]) -> str:
        """Tạo MD5 hash từ chuỗi đặc điểm để làm key tra cứu nhanh"""
        raw_str = f"{self.by}:{self.value}"
        return hashlib.md5(raw_str.encode("utf-8")).hexdigest()