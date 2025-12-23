# File: proactive_fault_prevention/data_fetcher.py
import psycopg2
from proactive_fault_prevention.config import PG_DB_CONFIG

def get_db_connection():
    try:
        conn = psycopg2.connect(**PG_DB_CONFIG)
        return conn
    except Exception as e:
        print(f"ERROR: Cannot connect to PostgreSQL: {e}")
        raise

def get_project_repo_url(project_id):
    """
    Lấy Git URL từ bảng Projects.
    Lưu ý: Bạn cần đảm bảo bảng management.projects có cột chứa URL (vd: git_url).
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Giả định bảng projects tên là management.projects
        query = "SELECT repo_url FROM management.projects WHERE project_id = %s"
        cur.execute(query, (project_id,))
        row = cur.fetchone()
        
        if row:
            return row[0]
        return None
    except Exception as e:
        raise Exception(f"DB Error fetching project: {str(e)}")
    finally:
        if conn: conn.close()

def get_testcase_details(case_id):
    """
    Lấy thông tin Test Case và Steps sử dụng chính xác câu SQL mẫu.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Query thông tin Test Case (Y hệt mẫu bạn cung cấp)
        # Lưu ý: Mẫu này KHÔNG trả về file_path, nên ta sẽ phải xử lý ở tầng trên.
        cur.execute("""
            SELECT case_id, name, priority, case_type, description, suite_id,
                   fullscreen_page_name, app_version
            FROM management.test_cases
            WHERE case_id = %s
        """, (case_id,))
        
        row = cur.fetchone()
        if not row:
            raise Exception(f"Test case ID {case_id} not found in DB")
            
        # Map dữ liệu từ row
        case_info = {
            "case_id": row[0],
            "test_name": row[1],         # Tên hàm test hoặc tên test case
            "priority": row[2],
            "case_type": row[3],
            "description": row[4],
            "suite_id": row[5],
            "author": "system-db",       # Mặc định vì không có cột author trong select
            "file_path": None            # DB mẫu không có cột file_path -> Cần lấy từ API Request
        }

        # 2. Query Test Steps (Y hệt mẫu bạn cung cấp)
        cur.execute("""
            SELECT step_order, action, locator_type, locator_value, value, url, expected
            FROM management.test_steps
            WHERE case_id = %s
            ORDER BY step_order ASC
        """, (case_id,))
        
        steps = []
        for s in cur:
            steps.append({
                "order": s[0],
                "action": s[1],
                "locator_type": s[2],
                "locator_value": s[3],
                "value": s[4],
                "url": s[5],
                "expected": s[6]
            })
            
        case_info["steps"] = steps
        return case_info

    except Exception as e:
        raise Exception(f"DB Error fetching testcase: {str(e)}")
    finally:
        if conn: conn.close()