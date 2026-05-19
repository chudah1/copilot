"""add signal linking columns to monitoring_events

Revision ID: 20260515_signal_linking
Revises: 20260513_add_thesis_reviews
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa

from app.database import UUIDType


revision = "20260515_signal_linking"
down_revision = "20260513_add_thesis_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("monitoring_events", sa.Column("claim_id", UUIDType(), nullable=True))
    op.add_column("monitoring_events", sa.Column("signal_id", UUIDType(), nullable=True))
    op.add_column("monitoring_events", sa.Column("evidence_type", sa.String(length=30), nullable=True))
    op.add_column("monitoring_events", sa.Column("evidence_summary", sa.Text(), nullable=True))
    op.add_column("monitoring_events", sa.Column("verdict", sa.String(length=20), nullable=True))
    op.create_index("ix_monitoring_events_claim_id", "monitoring_events", ["claim_id"])
    op.create_index("ix_monitoring_events_signal_id", "monitoring_events", ["signal_id"])


def downgrade() -> None:
    op.drop_index("ix_monitoring_events_signal_id", table_name="monitoring_events")
    op.drop_index("ix_monitoring_events_claim_id", table_name="monitoring_events")
    op.drop_column("monitoring_events", "verdict")
    op.drop_column("monitoring_events", "evidence_summary")
    op.drop_column("monitoring_events", "evidence_type")
    op.drop_column("monitoring_events", "signal_id")
    op.drop_column("monitoring_events", "claim_id")
