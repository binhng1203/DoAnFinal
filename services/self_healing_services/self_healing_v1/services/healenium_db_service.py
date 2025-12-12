import logging
import json
import psycopg2
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class HealeniumDBService:
    """
    Service kết nối tới PostgreSQL của Healenium để lấy metadata của Selector.
    Mục đích: Cung cấp dữ liệu 'Hồ sơ gốc' (Tag, Text, Class, Attributes...) 
    cho Healing Layer để so sánh chính xác hơn.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Fallback giá trị mặc định nếu config là None
        config = config or {}
        
        # Cấu hình kết nối (Default là cấu hình chuẩn của Healenium Docker)
        self.host = config.get("host", "localhost")
        self.port = int(config.get("port", 5432))
        self.user = config.get("user", "healenium_user")      # User DB của Healenium
        self.password = config.get("password", "healenium_pass") # Pass DB của Healenium
        self.dbname = config.get("dbname", "healenium")       # Tên DB

    def get_selector_info(self, locator_value: str) -> Optional[Dict[str, Any]]:
        """
        Query bảng 'selector' để lấy thông tin chi tiết (tag, class, text...) 
        dựa trên locator string (value).
        """
        # Câu query lấy thông tin mới nhất của locator này
        query = """
            SELECT command_info 
            FROM selector 
            WHERE locator = %s 
            ORDER BY created_date DESC 
            LIMIT 1
        """
        
        conn = None
        try:
            # Tạo kết nối tới DB
            conn = psycopg2.connect(
                host=self.host, 
                port=self.port, 
                user=self.user, 
                password=self.password, 
                dbname=self.dbname
            )
            
            cursor = conn.cursor()
            cursor.execute(query, (locator_value,))
            row = cursor.fetchone()
            
            if row:
                # Healenium lưu JSON trong cột command_info
                # Dữ liệu trả về thường có dạng:
                # {
                #   "id": "btn-login",
                #   "tagName": "button",
                #   "classes": ["btn", "btn-primary"],
                #   "innerText": "Đăng nhập",
                #   "otherAttributes": {"type": "submit"}
                # }
                raw_data = row[0]
                
                # psycopg2 có thể tự parse JSONB, nếu chưa thì parse thủ công
                if isinstance(raw_data, str):
                    return json.loads(raw_data)
                return raw_data 
                
        except psycopg2.Error as e:
            # Log lỗi DB nhưng không làm crash test (trả về None để dùng Fallback)
            logger.debug(f"[HealeniumDB] Lỗi kết nối/query DB: {e}")
        except Exception as e:
            logger.debug(f"[HealeniumDB] Lỗi xử lý dữ liệu selector '{locator_value}': {e}")
        finally:
            if conn:
                conn.close()
            
        return None