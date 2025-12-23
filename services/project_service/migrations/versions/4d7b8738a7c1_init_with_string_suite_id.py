"""Init with String Suite ID

Revision ID: 4d7b8738a7c1
Revises:
Create Date: 2025-12-06 10:29:23.142836
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4d7b8738a7c1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # đảm bảo schema tồn tại
    op.execute("CREATE SCHEMA IF NOT EXISTS management")

    # 🔥 DROP INDEX AN TOÀN
    op.execute("DROP INDEX IF EXISTS idx_kb_app_version")

    # 🔥 DROP TABLE AN TOÀN
    op.execute("DROP TABLE IF EXISTS healing_knowledge")

    # --- management tables ---
    op.create_table(
        'projects',
        sa.Column('project_id', sa.String(length=8), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('repo_url', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False
        ),
        sa.PrimaryKeyConstraint('project_id'),
        schema='management'
    )

    op.create_table(
        'project_members',
        sa.Column('project_id', sa.String(length=8), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_role', sa.String(length=30), nullable=False),
        sa.Column(
            'joined_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.CheckConstraint(
            "project_role IN ('Project Admin', 'Member')",
            name='check_project_role_valid'
        ),
        sa.ForeignKeyConstraint(
            ['project_id'],
            ['management.projects.project_id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('project_id', 'user_id'),
        schema='management'
    )

    op.create_table(
        'test_suites',
        sa.Column('suite_id', sa.String(length=255), nullable=False),
        sa.Column('project_id', sa.String(length=8), nullable=False),
        sa.Column('parent_suite_id', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ['parent_suite_id'],
            ['management.test_suites.suite_id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['project_id'],
            ['management.projects.project_id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('suite_id'),
        schema='management'
    )

    op.create_table(
        'test_cases',
        sa.Column('case_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('suite_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=True),
        sa.Column('case_type', sa.String(length=20), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('assignee_id', sa.String(length=36), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('fullscreen_page_name', sa.String(length=255), nullable=True),
        sa.Column('app_version', sa.String(length=50), nullable=True),
        sa.Column('last_run_status', sa.String(length=20), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True
        ),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('updated_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ['suite_id'],
            ['management.test_suites.suite_id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('case_id'),
        schema='management'
    )

    op.create_table(
        'test_steps',
        sa.Column('step_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('locator_type', sa.String(length=50), nullable=True),
        sa.Column('locator_value', sa.Text(), nullable=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('expected', sa.Text(), nullable=True),
        sa.Column('url', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ['case_id'],
            ['management.test_cases.case_id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('step_id'),
        schema='management'
    )


def downgrade():
    # Drop management tables
    op.drop_table('test_steps', schema='management')
    op.drop_table('test_cases', schema='management')
    op.drop_table('test_suites', schema='management')
    op.drop_table('project_members', schema='management')
    op.drop_table('projects', schema='management')

    # Recreate healing_knowledge table
    op.create_table(
        'healing_knowledge',
        sa.Column('id', sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.VARCHAR(length=8), nullable=True),
        sa.Column('fingerprint', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('old_locator_by', sa.VARCHAR(length=50), nullable=False),
        sa.Column('old_locator_value', sa.TEXT(), nullable=False),
        sa.Column('new_locator_by', sa.VARCHAR(length=50), nullable=False),
        sa.Column('new_locator_value', sa.TEXT(), nullable=False),
        sa.Column('success_count', sa.INTEGER(), server_default=sa.text('0'), nullable=False),
        sa.Column('failure_count', sa.INTEGER(), server_default=sa.text('0'), nullable=False),
        sa.Column('avg_repair_ms', sa.BIGINT(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_success_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_failure_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('commit_info', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            'source_type',
            sa.TEXT(),
            server_default=sa.text("'AUTO'::text"),
            nullable=False
        ),
        sa.Column('app_version', sa.TEXT(), nullable=True),
        sa.Column(
            'last_updated',
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False
        ),
        sa.CheckConstraint('avg_repair_ms >= 0'),
        sa.CheckConstraint('failure_count >= 0'),
        sa.CheckConstraint('success_count >= 0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'fingerprint',
            'old_locator_value',
            'new_locator_value',
            name='uq_kb'
        )
    )

    # Recreate index
    op.create_index(
        'idx_kb_app_version',
        'healing_knowledge',
        ['app_version'],
        unique=False
    )