"""add decision_snapshots table

Capture half of the decision-mirror loop: a snapshot of each conviction call plus
the state of what the user was betting on, so the outcome can be read back later.

Revision ID: 20260602_decision_snapshots
Revises: 20260531_last_monitored
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260602_decision_snapshots"
down_revision = "20260531_last_monitored"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "decision_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("thesis_id", sa.Uuid(), nullable=False),
        sa.Column("holding_id", sa.Uuid(), nullable=False),
        sa.Column("monitoring_event_id", sa.Uuid(), nullable=True),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("signal_id", sa.Uuid(), nullable=True),
        sa.Column("verdict", sa.String(30), nullable=False),
        sa.Column("bucket", sa.String(20), nullable=False),
        sa.Column("decision_source", sa.String(30), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("price_native", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("value_gbp", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("benchmark_ticker", sa.String(20), nullable=True),
        sa.Column("next_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bet_text", sa.Text(), nullable=True),
        sa.Column("condition_snapshot", sa.JSON(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"]),
        sa.ForeignKeyConstraint(["holding_id"], ["holdings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decision_snapshots_user_id", "decision_snapshots", ["user_id"])
    op.create_index("ix_decision_snapshots_thesis_id", "decision_snapshots", ["thesis_id"])
    op.create_index("ix_decision_snapshots_holding_id", "decision_snapshots", ["holding_id"])
    op.create_index("ix_decision_snapshots_bucket", "decision_snapshots", ["bucket"])
    op.create_index("ix_decision_snapshots_decided_at", "decision_snapshots", ["decided_at"])


def downgrade():
    op.drop_index("ix_decision_snapshots_decided_at", "decision_snapshots")
    op.drop_index("ix_decision_snapshots_bucket", "decision_snapshots")
    op.drop_index("ix_decision_snapshots_holding_id", "decision_snapshots")
    op.drop_index("ix_decision_snapshots_thesis_id", "decision_snapshots")
    op.drop_index("ix_decision_snapshots_user_id", "decision_snapshots")
    op.drop_table("decision_snapshots")
