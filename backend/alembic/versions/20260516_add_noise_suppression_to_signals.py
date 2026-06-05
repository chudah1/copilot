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


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("thesis_signals")
    if "last_fired_at" not in columns:
        op.add_column("thesis_signals", sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True))
    if "consecutive_ignores" not in columns:
        op.add_column("thesis_signals", sa.Column("consecutive_ignores", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    columns = _column_names("thesis_signals")
    if "consecutive_ignores" in columns:
        op.drop_column("thesis_signals", "consecutive_ignores")
    if "last_fired_at" in columns:
        op.drop_column("thesis_signals", "last_fired_at")
