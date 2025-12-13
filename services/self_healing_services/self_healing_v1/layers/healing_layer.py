import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from difflib import SequenceMatcher

from lxml import html
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Cấu hình Logger
logger = logging.getLogger(__name__)

class HealingLayer:
    """
    Layer 2: Healing Engine
    Nhiệm vụ: Phân tích DOM hiện tại (Snapshot), so sánh với thông tin Element gốc
    (từ DB hoặc Locator string) để tìm ứng viên thay thế tốt nhất.
    
    Công nghệ: 
    - lxml (DOM Parsing siêu tốc)
    - Weighted Scoring (Chấm điểm trọng số)
    - LCS (So sánh chuỗi con chung dài nhất)
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # --- CẤU HÌNH TRỌNG SỐ (WEIGHTS) ---
        # Tổng trọng số nên bằng 1.0. Bạn có thể điều chỉnh tùy dự án.
        self.weights = {
            "id": 0.25,        # ID: Quan trọng nhưng dễ bị đổi (dynamic id)
            "text": 0.30,      # Text: Quan trọng với người dùng (Button label, Link text)
            "class": 0.20,     # Class: Thể hiện cấu trúc/style
            "tag": 0.10,       # Tag: Ít khi đổi (VD: button -> a)
            "attributes": 0.15 # Các thuộc tính khác (name, href, type, role...)
        }
        
        # Ngưỡng chấp nhận: Chỉ lấy candidate có điểm >= mức này
        self.min_score_threshold = float(self.config.get("min_score", 0.65))

    def get_candidates(
        self, 
        driver: WebDriver, 
        by: str, 
        value: str, 
        selector_info: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Hàm chính để tìm kiếm phần tử thay thế.
        
        Args:
            driver: Selenium WebDriver instance.
            by: Loại locator gốc (By.ID, By.XPATH...).
            value: Giá trị locator gốc.
            selector_info: (Quan trọng) Dictionary chứa metadata từ bảng healenium.selector.
                           Nếu None, sẽ fallback sang parse chuỗi 'value'.
        
        Returns:
            List các candidates đã được chấm điểm, sắp xếp giảm dần.
        """
        logger.info(f"[HealingLayer] Bắt đầu quét DOM tìm candidate cho: {value}")

        # 1. Xây dựng Chân dung mục tiêu (Target Profile)
        # Đây là bước quyết định độ chính xác. Dữ liệu từ DB luôn tốt hơn regex string.
        if selector_info:
            logger.info("[HealingLayer] Sử dụng dữ liệu chi tiết từ Healenium Database.")
            target_profile = self._normalize_db_info(selector_info)
        else:
            logger.warning("[HealingLayer] Không có dữ liệu DB. Sử dụng Fallback (Parse String).")
            target_profile = self._parse_locator_string(value)
            
        logger.debug(f"[HealingLayer] Target Profile: {target_profile}")

        # 2. Lấy Snapshot DOM (Hiệu năng cao)
        # Lấy toàn bộ HTML 1 lần duy nhất, tránh gọi driver nhiều lần
        page_source = driver.page_source
        if not page_source:
            logger.error("[HealingLayer] Page source trống. Không thể healing.")
            return []

        try:
            # Parse HTML thành Tree Object trong RAM bằng lxml
            tree = html.fromstring(page_source)
        except Exception as e:
            logger.error(f"[HealingLayer] Lỗi parse DOM bằng lxml: {e}")
            return []

        # 3. Khoanh vùng tìm kiếm (Pre-filtering)
        # Chỉ quét các node cùng Tag để tối ưu tốc độ.
        # Nếu Tag gốc là '*', quét toàn bộ (chậm hơn).
        search_tag = target_profile['tag']
        if not search_tag or search_tag == '*':
            xpath_query = "body//*" # Quét toàn bộ body
        else:
            xpath_query = f"//{search_tag}"
            
        candidates_nodes = tree.xpath(xpath_query)
        logger.info(f"[HealingLayer] Tìm thấy {len(candidates_nodes)} node tiềm năng (Tag: '{search_tag}'). Đang chấm điểm...")

        scored_candidates = []

        # 4. Vòng lặp chấm điểm (The Core Algorithm)
        for node in candidates_nodes:
            # Bỏ qua các node script/style vô nghĩa
            if node.tag in ['script', 'style', 'noscript']:
                continue

            score, details = self._calculate_weighted_score(target_profile, node)
            
            if score >= self.min_score_threshold:
                # Chuyển đổi Node lxml ngược lại thành XPath để Selenium dùng được
                reconstructed_xpath = self._get_xpath_from_node(tree, node)
                
                candidate_data = {
                    "locator": (By.XPATH, reconstructed_xpath),
                    "value": reconstructed_xpath,
                    "score": score,
                    "source": "healing_layer_db" if selector_info else "healing_layer_fallback",
                    "details": details # Lý do tại sao chọn (dùng cho Decision Layer & Logging)
                }
                scored_candidates.append(candidate_data)

        # 5. Sắp xếp & Trả về
        # Sort điểm cao nhất lên đầu
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Chỉ lấy Top 5 để giảm tải cho các layer sau
        top_candidates = scored_candidates[:5]
        
        if top_candidates:
            best = top_candidates[0]
            logger.info(f"[HealingLayer] Best Candidate: Score {best['score']:.2f} | Details: {best['details']}")
        else:
            logger.info("[HealingLayer] Không tìm thấy ứng viên nào vượt qua ngưỡng điểm.")

        return top_candidates

    # ========================================================
    # LOGIC TÍNH ĐIỂM (WEIGHTED SCORING ENGINE)
    # ========================================================

    def _calculate_weighted_score(self, target: Dict[str, Any], node) -> Tuple[float, Dict[str, Any]]:
        """
        Tính điểm tương đồng giữa Target (Gốc) và Node (Hiện tại).
        Trả về: (Total Score, Details Dictionary)
        """
        current_score = 0.0
        details = {}

        # --- 1. ID Score (Sử dụng LCS) ---
        node_id = node.get('id', '')
        if target['id'] and node_id:
            sim = self._lcs_similarity(target['id'], node_id)
            current_score += sim * self.weights['id']
            if sim > 0.5: details['id'] = f"{sim:.2f}"
        
        # --- 2. Text Score (Sử dụng LCS) ---
        # lxml text_content() lấy cả text của con, strip() để loại bỏ whitespace thừa
        node_text = (node.text_content() or "").strip()
        target_text = target['text']
        
        if target_text:
            if node_text:
                sim = self._lcs_similarity(target_text, node_text)
                current_score += sim * self.weights['text']
                if sim > 0.5: details['text'] = f"{sim:.2f}"
        else:
            # Nếu target gốc không có text, ta có thể bỏ qua hoặc chia lại trọng số.
            # Ở đây giữ nguyên logic đơn giản: không cộng điểm text.
            pass

        # --- 3. Class Score (Sử dụng Jaccard Index) ---
        # Class là tập hợp, ví dụ ['btn', 'btn-primary']
        node_classes = set(node.get('class', '').split())
        target_classes = set(target['class'])
        
        if target_classes and node_classes:
            intersection = target_classes.intersection(node_classes)
            union = target_classes.union(node_classes)
            if union:
                # Jaccard = Giao / Hợp
                jaccard_index = len(intersection) / len(union)
                current_score += jaccard_index * self.weights['class']
                if jaccard_index > 0.3: details['class'] = f"{len(intersection)} matched"

        # --- 4. Tag Score (Exact Match) ---
        if node.tag == target['tag']:
            current_score += self.weights['tag']

        # --- 5. Other Attributes Score ---
        # So sánh các attribute khác như name, href, type...
        target_attrs = target['attributes']
        if target_attrs:
            match_count = 0
            total_checked = 0
            for k, v in target_attrs.items():
                if k in ['id', 'class']: continue # Đã tính riêng
                
                total_checked += 1
                node_val = node.get(k)
                if node_val and str(node_val) == str(v): # So sánh bằng tương đối
                    match_count += 1
            
            if total_checked > 0:
                attr_ratio = match_count / total_checked
                current_score += attr_ratio * self.weights['attributes']
                if attr_ratio > 0: details['attrs'] = f"{match_count}/{total_checked}"

        return current_score, details

    # ========================================================
    # HELPER FUNCTIONS (TIỆN ÍCH)
    # ========================================================

    def _lcs_similarity(self, s1: str, s2: str) -> float:
        """Tính độ tương đồng chuỗi con chung dài nhất (LCS) - 0.0 đến 1.0"""
        if not s1 or not s2: return 0.0
        return SequenceMatcher(None, s1, s2).ratio()

    def _get_xpath_from_node(self, tree, node) -> str:
        """Lấy XPath tuyệt đối của node từ lxml tree"""
        return tree.getpath(node)

    def _normalize_db_info(self, db_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Chuẩn hóa dữ liệu JSON từ Healenium DB về format nội bộ.
        Healenium thường lưu: {tagName: '...', id: '...', classes: [...], innerText: '...'}
        """
        classes = db_info.get('classes') or []
        # Đề phòng trường hợp classes lưu dưới dạng string thay vì list
        if isinstance(classes, str):
            classes = classes.split()

        return {
            'tag': db_info.get('tagName', '*'),
            'id': db_info.get('id') or '',
            'text': db_info.get('innerText') or '',
            'class': classes,
            'attributes': db_info.get('otherAttributes') or {}
        }

    def _parse_locator_string(self, value: str) -> Dict[str, Any]:
        """
        Fallback: Cố gắng trích xuất thông tin từ chuỗi XPath/CSS cũ.
        Hỗ trợ: text(), contains(), normalize-space()
        """
        profile = {
            'tag': '*',
            'id': '',
            'text': '',
            'class': [],
            'attributes': {}
        }
        
        # 1. Tag (//button...)
        tag_match = re.search(r"//([\w\-]+)", value)
        if tag_match: profile['tag'] = tag_match.group(1)
        
        # 2. ID (@id='...')
        id_match = re.search(r"@id=['\"](.*?)['\"]", value)
        if id_match: profile['id'] = id_match.group(1)
        
        # 3. Text (Logic quan trọng)
        # Case A: text()='...'
        text_match = re.search(r"text\(\)\s*=\s*['\"](.*?)['\"]", value)
        
        # Case B: contains(text(), '...')
        text_cont = re.search(r"contains\(text\(\)\s*,\s*['\"](.*?)['\"]", value)
        
        # Case C: normalize-space()='...'  <-- CẦN THÊM CÁI NÀY
        text_norm = re.search(r"normalize-space\(\)\s*=\s*['\"](.*?)['\"]", value)

        if text_match: 
            profile['text'] = text_match.group(1)
        elif text_cont: 
            profile['text'] = text_cont.group(1)
        elif text_norm: 
            profile['text'] = text_norm.group(1) # <--- Bắt được text "Add to Cart"

        # 4. Class (@class='...')
        class_match = re.search(r"@class=['\"](.*?)['\"]", value)
        if class_match: profile['class'] = class_match.group(1).split()

        return profile