"""add monitoring_gaps table

Track failures in the monitoring pipeline so operators can see when coverage dropped.

Revision ID: 20260607_add_monitoring_gap
Revises: 20260603_avg_cost_native
Create Date: 2026-06-07
"""
from alembic import op
import sqlalchemy as sa

revision = "20260607_add_monitoring_gap"
down_revision = "20260603_avg_cost_native"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "monitoring_gaps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thesis_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("run_id", sa.String(100), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitoring_gaps_thesis_id", "monitoring_gaps", ["thesis_id"])


def downgrade():
    op.drop_index("ix_monitoring_gaps_thesis_id", "monitoring_gaps")
    op.drop_table("monitoring_gaps")
