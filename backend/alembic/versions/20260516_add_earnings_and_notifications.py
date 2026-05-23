"""Add earnings_calendar and user_notifications tables.

Revision ID: 20260516_earnings_notifications
Revises: 20260516_conviction_log
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa

from app.database import UUIDType

revision = "20260516_earnings_notifications"
down_revision = "20260516_conviction_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "earnings_calendar",
        sa.Column("id", UUIDType(), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False, unique=True, index=True),
        sa.Column("report_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="yfinance"),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "user_notifications",
        sa.Column("id", UUIDType(), primary_key=True),
        sa.Column("user_id", UUIDType(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("notification_type", sa.String(30), nullable=False, index=True),
        sa.Column("holding_id", UUIDType(), sa.ForeignKey("holdings.id"), nullable=True),
        sa.Column("thesis_id", UUIDType(), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_notifications")
    op.drop_table("earnings_calendar")
