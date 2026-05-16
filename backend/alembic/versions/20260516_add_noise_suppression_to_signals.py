"""Add last_fired_at and consecutive_ignores to thesis_signals.

Revision ID: 20260516_noise_suppression
Revises: 20260515_signal_linking
Create Date: 2026-05-16
"""
from alembic import op
import sqlalchemy as sa


revision = "20260516_noise_suppression"
down_revision = "20260515_signal_linking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("thesis_signals", sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("thesis_signals", sa.Column("consecutive_ignores", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("thesis_signals", "consecutive_ignores")
    op.drop_column("thesis_signals", "last_fired_at")
