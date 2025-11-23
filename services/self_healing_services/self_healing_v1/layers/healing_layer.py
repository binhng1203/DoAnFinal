# self_healing_v1/layers/healing_layer.py

import logging
import re
from typing import List, Dict, Any, Optional, Tuple

import requests  # giữ lại để tương thích / mở rộng sau này
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import StaleElementReferenceException

logger = logging.getLogger(__name__)


# ===================== JARO–WINKLER =====================

def jaro_winkler_similarity(s1, s2) -> float:
    """Tính độ tương đồng Jaro-Winkler giữa 2 chuỗi (trả về 0–1)."""
    if not s1 or not s2:
        return 0.0

    s1, s2 = str(s1), str(s2)
    len1, len2 = len(s1), len(s2)

    match_distance = (max(len1, len2) // 2) - 1
    matches1, matches2 = [False] * len1, [False] * len2
    matches = 0
    transpositions = 0

    # Đếm matches
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if not matches2[j] and s1[i] == s2[j]:
                matches1[i] = True
                matches2[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    # Đếm transpositions
    k = 0
    for i in range(len1):
        if matches1[i]:
            while not matches2[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

    transpositions //= 2
    jaro_similarity = (
        matches / len1
        + matches / len2
        + (matches - transpositions) / matches
    ) / 3.0

    # Prefix (Winkler)
    prefix = 0
    for i in range(min(len1, len2)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
        if prefix == 4:
            break

    final_score = jaro_similarity + (prefix * 0.1 * (1.0 - jaro_similarity))
    return max(0.0, min(1.0, final_score))


class HealingLayer:
    """
    HealingLayer PYTHON – tầng fallback sau Healenium + KB.

    API workflow mới:
        HealingManager gọi:
            candidates = healing_layer.get_candidates(driver, by, value)

    Candidates trả về format:
        {
          "by": "xpath",
          "value": "...",
          "score": 0.xx,
          "source": "heuristics"
        }
    """

    def __init__(
        self,
        driver: Optional[WebDriver] = None,
        healenium_host: str = "http://localhost:7878",
        request_timeout: float = 10.0,
        disable_healing: bool = False,
        session: Optional[requests.Session] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.driver = driver
        self.request_timeout = request_timeout
        self.disable_healing = disable_healing
        self._session = session or requests.Session()
        self.config = config or {}

        self.backend_url = healenium_host.rstrip("/")

        logger.info(
            "[HealingLayer] Init (workflow mới). "
            "Healenium là engine chính, layer Python chỉ dùng heuristics fallback. "
            f"Healenium-backend (chỉ tham chiếu): {self.backend_url}"
        )

    # ===================== PUBLIC =====================

    def get_candidates(self, driver: WebDriver, by, value) -> List[Dict[str, Any]]:
        """
        Hàm PUBLIC mà HealingManager workflow mới gọi.
        """
        if self.disable_healing:
            logger.info("[HealingLayer] Healing bị tắt (disable_healing=True).")
            return []

        if self.driver is None:
            self.driver = driver

        broken_tag, broken_text = self._parse_broken_locator(by, value)

        logger.info(
            "[HealingLayer] BẮT ĐẦU fallback bằng heuristics. "
            f"Broken locator: by={by}, value={value}, "
            f"tag='{broken_tag}', text='{broken_text}'"
        )

        heuristic_candidates = self._heuristic_candidates(
            driver, broken_tag, broken_text
        )

        merged = self._dedup_and_sort(heuristic_candidates)
        logger.info(f"[HealingLayer] Candidates (fallback): total={len(merged)}")
        return merged

    # Alias để tương thích những chỗ code cũ (nếu còn)
    def generate_candidates(self, driver: WebDriver, by, value) -> List[Dict[str, Any]]:
        return self.get_candidates(driver, by, value)

    # ===================== PRIVATE – HEURISTICS =====================

    def _heuristic_candidates(
        self,
        driver: WebDriver,
        broken_tag: str,
        broken_text: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not broken_text:
            logger.debug(
                "[HealingLayer] [Heuristics] Không tìm được text trong locator hỏng."
            )
            return []

        min_score = float(self.config.get("min_similarity", 0.5))

        logger.info(
            "[HealingLayer] [Heuristics] Đang tìm ứng viên cho: "
            f"tag='{broken_tag}', text='{broken_text}', min_score={min_score}"
        )

        candidates: List[Dict[str, Any]] = []

        try:
            if broken_tag == "*" or not broken_tag:
                elements_on_page = driver.find_elements(By.XPATH, "//*")
            else:
                elements_on_page = driver.find_elements(By.TAG_NAME, broken_tag)
        except Exception as e:
            logger.error(
                "[HealingLayer] [Heuristics] Lỗi khi quét DOM theo tag '%s': %s",
                broken_tag,
                e,
            )
            return []

        for element in elements_on_page:
            try:
                candidate_text = element.text or ""
                if not candidate_text:
                    continue

                score = jaro_winkler_similarity(candidate_text, broken_text)
                if score < min_score:
                    continue

                candidate_xpath = self._generate_stable_xpath(element)
                if candidate_xpath:
                    candidates.append(
                        {
                            "by": "xpath",  # DecisionLayer sẽ map sang By.XPATH
                            "value": candidate_xpath,
                            "score": score,
                            "source": "heuristics",
                        }
                    )
            except StaleElementReferenceException:
                continue
            except Exception:
                continue

        return candidates

    # ===================== HELPERS =====================

    def _parse_broken_locator(self, by: str, value: str) -> Tuple[str, Optional[str]]:
        """
        Phân tích locator bị hỏng (ưu tiên XPath).

        Support:
          - by == By.XPATH
          - by == "xpath" (string)
        """
        by_str = by.value if hasattr(by, "value") else str(by)
        if by != By.XPATH and by_str.lower() != "xpath":
            return "*", None

        # Lấy tag từ đầu XPath: //button[...] -> button
        tag_match = re.search(r"^\/\/(?P<tag>[\w\*]+)", value or "")
        tag = tag_match.group("tag") if tag_match else "*"

        # text()='XYZ'
        text_match = re.search(
            r"text\(\)\s*=\s*['\"](?P<text>.*?)['\"]", value or ""
        )
        if text_match:
            return tag, text_match.group("text")

        # contains(text(),'XYZ')
        text_match_contains = re.search(
            r"contains\s*\(\s*text\(\)\s*,\s*['\"](?P<text>.*?)['\"]",
            value or "",
        )
        if text_match_contains:
            return tag, text_match_contains.group("text")

        # normalize-space(.)='XYZ'
        text_match_norm = re.search(
            r"normalize-space\s*\(\s*\.\s*\)\s*=\s*['\"](?P<text>.*?)['\"]",
            value or "",
        )
        if text_match_norm:
            return tag, text_match_norm.group("text")

        return tag, None

    def _generate_stable_xpath(self, element: WebElement) -> Optional[str]:
        """
        Sinh XPath "ổn định" cho 1 element:
          - Nếu có id => //*[@id='...']
          - Nếu có text => //tag[normalize-space()='TEXT']
        """
        try:
            el_id = element.get_attribute("id")
            if el_id:
                return f"//*[@id='{el_id}']"

            el_text = element.text or ""
            if el_text:
                safe_text = el_text.replace("'", "").replace('"', "").strip()
                if safe_text:
                    return f"//{element.tag_name}[normalize-space()='{safe_text}']"

            return None
        except StaleElementReferenceException:
            return None
        except Exception:
            return None

    def _dedup_and_sort(self, arr: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        uniq: List[Dict[str, Any]] = []

        for c in arr:
            k = (c.get("by"), c.get("value"))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(c)

        uniq.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
        return uniq
