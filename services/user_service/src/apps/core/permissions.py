from rest_framework.permissions import BasePermission
from django.db import connection

def user_has_role(user_id, role_name: str) -> bool:
    with connection.cursor() as cur:
        cur.execute("""
            SELECT 1
            FROM core.user_roles ur
            JOIN core.roles r ON r.role_id = ur.role_id
            WHERE ur.user_id = %s AND r.role_name = %s
            LIMIT 1
        """, [str(user_id), role_name])
        return cur.fetchone() is not None

class IsAdminRole(BasePermission):
    message = "Admin privileges required."
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        return user_has_role(u.user_id, "Admin")

