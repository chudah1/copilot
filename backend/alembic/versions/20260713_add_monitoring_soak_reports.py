"""Add monitoring soak reports table

Revision ID: 20260713_soak_reports
Revises: 20260710_story_anchor
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260713_soak_reports"
down_revision = "20260710_story_anchor"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "monitoring_soak_reports" in existing_tables:
        return

    op.create_table(
        "monitoring_soak_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("basket_config", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_monitoring_soak_reports_run_id",
        "monitoring_soak_reports",
        ["run_id"],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "monitoring_soak_reports" not in existing_tables:
        return
    indexes = {index["name"] for index in inspector.get_indexes("monitoring_soak_reports")}
    if "ix_monitoring_soak_reports_run_id" in indexes:
        op.drop_index("ix_monitoring_soak_reports_run_id", table_name="monitoring_soak_reports")
    op.drop_table("monitoring_soak_reports")
