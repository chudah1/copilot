"""add thesis_health_snapshots table

Revision ID: 20260527_health_snapshots
Revises: 20260527_signal_label_refresh
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260527_health_snapshots"
down_revision = "20260527_signal_label_refresh"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "thesis_health_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thesis_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(10), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_thesis_health_snapshots_thesis_id", "thesis_health_snapshots", ["thesis_id"])


def downgrade():
    op.drop_index("ix_thesis_health_snapshots_thesis_id", "thesis_health_snapshots")
    op.drop_table("thesis_health_snapshots")
