"""add label_refreshed_at to thesis_signals

Revision ID: 20260527_signal_label_refresh
Revises: 20260527_waitlist
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260527_signal_label_refresh"
down_revision = "20260527_waitlist"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "thesis_signals",
        sa.Column("label_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("thesis_signals", "label_refreshed_at")
