# db_loader.py
import psycopg2
from psycopg2.extras import RealDictCursor


def load_test_definition_from_db(test_case_id: str, db_config: dict):
    """
    Load testcase + steps từ DB và build test_definition.

    test_case_id: test_cases.case_id (UUID dạng string).
    db_config: host, port, dbname, user, password.
    """

    conn = psycopg2.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
    )

    try:
        # 1. Lấy thông tin test_case
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT case_id,
                       name,
                       priority,
                       type,
                       description,
                       assignee_user_id,
                       suite_id,
                       tags,
                       last_run_status,
                       last_run_at,
                       fullscreen_page_name,
                       app_version,
                       build_version,
                       git_hash,
                       created_by,
                       updated_by,
                       created_at,
                       updated_at,
                       is_active
                FROM test_cases
                WHERE case_id = %s
            """, (test_case_id,))
            tc = cur.fetchone()

        if not tc:
            return None

        test_definition = {
            # ID kỹ thuật (uuid) để lưu log/report
            "test_id": str(tc["case_id"]),
            # Tên test case để hiển thị
            "name": tc["name"],
            "priority": tc["priority"],
            "type": tc["type"],
            "description": tc["description"],
            # assignee sẽ được dùng làm author khi chạy
            "assignee_user_id": tc["assignee_user_id"],
            "suite_id": tc["suite_id"],
            "tags": tc["tags"],
            "fullscreen_page_name": tc["fullscreen_page_name"] or "default",
            "app_version": tc["app_version"],
            "build_version": tc["build_version"],
            "git_hash": tc["git_hash"],
            "steps": []
        }

        # 2. Lấy list steps
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT step_order,
                       action,
                       locator_type,
                       locator_value,
                       value,
                       url,
                       expected
                FROM test_steps
                WHERE test_case_id = %s
                ORDER BY step_order ASC
            """, (test_case_id,))

            for row in cur.fetchall():
                test_definition["steps"].append({
                    "order": row["step_order"],
                    "action": row["action"],
                    "locator_type": row["locator_type"],
                    "locator_value": row["locator_value"],
                    "value": row["value"],
                    "url": row["url"],
                    "expected": row["expected"],
                })

        return test_definition

    finally:
        conn.close()
