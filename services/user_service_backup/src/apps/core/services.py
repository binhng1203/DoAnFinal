from typing import Iterable
from django.db import connection

def assign_roles(user_id, role_ids: Iterable[int]) -> int:
    inserted = 0
    with connection.cursor() as cur:
        for rid in role_ids:
            cur.execute("""
              INSERT INTO core.user_roles (user_id, role_id)
              VALUES (%s, %s)
              ON CONFLICT (user_id, role_id) DO NOTHING
            """, [str(user_id), rid])
            inserted += cur.rowcount if cur.rowcount else 0
    return inserted

