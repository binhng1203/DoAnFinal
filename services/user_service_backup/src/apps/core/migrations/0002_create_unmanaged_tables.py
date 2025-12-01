from django.db import migrations

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS core.user_roles (
  user_id UUID NOT NULL REFERENCES core.users(user_id) ON DELETE CASCADE,
  role_id INTEGER NOT NULL REFERENCES core.roles(role_id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS core.role_permissions (
  role_id INTEGER NOT NULL REFERENCES core.roles(role_id) ON DELETE CASCADE,
  permission_id INTEGER NOT NULL REFERENCES core.permissions(permission_id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);
"""

REVERSE_SQL = r"""
DROP TABLE IF EXISTS core.role_permissions;
DROP TABLE IF EXISTS core.user_roles;
"""

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_create_core_schema_and_tables'), # Phụ thuộc vào file 0001
    ]

    operations = [
        migrations.RunSQL(SCHEMA_SQL, REVERSE_SQL)
    ]