"""Add conviction_log_entries table.

Revision ID: 20260516_conviction_log
Revises: 20260516_noise_suppression
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa

revision = "20260516_conviction_log"
down_revision = "20260516_noise_suppression"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conviction_log_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("thesis_id", sa.String(36), sa.ForeignKey("theses.id"), nullable=False, index=True),
        sa.Column("holding_id", sa.String(36), sa.ForeignKey("holdings.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("entry_type", sa.String(30), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("claim_id", sa.String(36), nullable=True),
        sa.Column("signal_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("conviction_log_entries")
