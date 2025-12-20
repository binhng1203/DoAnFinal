# runner/db_loader.py
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

def fetch_test_case_data(test_case_id: int, db_config: dict):
    """
    Hàm lấy dữ liệu test case từ schema management.
    Tên hàm: fetch_test_case_data (phải khớp 100% với api.py)
    """
    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Lấy thông tin case
            cur.execute("""
                SELECT case_id, name, priority, fullscreen_page_name, app_version 
                FROM management.test_cases 
                WHERE case_id = %s
            """, (test_case_id,))
            case = cur.fetchone()
            
            if not case:
                return None, []

            # Lấy thông tin steps
            cur.execute("""
                SELECT step_order as "order", action, locator_type, locator_value, 
                       value, url, expected
                FROM management.test_steps 
                WHERE case_id = %s 
                ORDER BY step_order ASC
            """, (test_case_id,))
            steps = cur.fetchall()
            
            return case, steps
    except Exception as e:
        logger.error(f"Database Error: {str(e)}")
        return None, []
    finally:
        if conn:
            conn.close()