"""Add conviction_log_entries table.

Revision ID: 20260516_conviction_log
Revises: 20260516_noise_suppression
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa

from app.database import UUIDType

revision = "20260516_conviction_log"
down_revision = "20260516_noise_suppression"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conviction_log_entries",
        sa.Column("id", UUIDType(), primary_key=True),
        sa.Column("thesis_id", UUIDType(), sa.ForeignKey("theses.id"), nullable=False, index=True),
        sa.Column("holding_id", UUIDType(), sa.ForeignKey("holdings.id"), nullable=False, index=True),
        sa.Column("user_id", UUIDType(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("entry_type", sa.String(30), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("claim_id", UUIDType(), nullable=True),
        sa.Column("signal_id", UUIDType(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("conviction_log_entries")
