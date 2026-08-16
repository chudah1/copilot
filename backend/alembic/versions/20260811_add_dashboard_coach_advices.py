"""add dashboard coach advices

Revision ID: 20260811_add_dashboard_coach_advices
Revises: 20260810_open_loops
Create Date: 2026-08-11 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260811_add_dashboard_coach_advices"
down_revision: str | None = "20260810_open_loops"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dashboard_coach_advices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("advice_key", sa.String(length=160), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("holding_id", sa.UUID(), nullable=True),
        sa.Column("thesis_id", sa.UUID(), nullable=True),
        sa.Column("decision_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("loop_key", sa.String(length=200), nullable=True),
        sa.Column("pattern_kind", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("presented_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("acted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_presented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_presented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_skipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_action_label", sa.String(length=120), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_kind", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["decision_snapshot_id"], ["decision_snapshots.id"]),
        sa.ForeignKeyConstraint(["holding_id"], ["holdings.id"]),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "advice_key", name="uq_dashboard_coach_advices_user_advice"),
    )
    op.create_index(op.f("ix_dashboard_coach_advices_user_id"), "dashboard_coach_advices", ["user_id"], unique=False)
    op.create_index(op.f("ix_dashboard_coach_advices_advice_key"), "dashboard_coach_advices", ["advice_key"], unique=False)
    op.create_index(op.f("ix_dashboard_coach_advices_mode"), "dashboard_coach_advices", ["mode"], unique=False)
    op.create_index(op.f("ix_dashboard_coach_advices_holding_id"), "dashboard_coach_advices", ["holding_id"], unique=False)
    op.create_index(op.f("ix_dashboard_coach_advices_thesis_id"), "dashboard_coach_advices", ["thesis_id"], unique=False)
    op.create_index(op.f("ix_dashboard_coach_advices_decision_snapshot_id"), "dashboard_coach_advices", ["decision_snapshot_id"], unique=False)
    op.create_index(op.f("ix_dashboard_coach_advices_loop_key"), "dashboard_coach_advices", ["loop_key"], unique=False)
    op.create_index(op.f("ix_dashboard_coach_advices_status"), "dashboard_coach_advices", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dashboard_coach_advices_status"), table_name="dashboard_coach_advices")
    op.drop_index(op.f("ix_dashboard_coach_advices_loop_key"), table_name="dashboard_coach_advices")
    op.drop_index(op.f("ix_dashboard_coach_advices_decision_snapshot_id"), table_name="dashboard_coach_advices")
    op.drop_index(op.f("ix_dashboard_coach_advices_thesis_id"), table_name="dashboard_coach_advices")
    op.drop_index(op.f("ix_dashboard_coach_advices_holding_id"), table_name="dashboard_coach_advices")
    op.drop_index(op.f("ix_dashboard_coach_advices_mode"), table_name="dashboard_coach_advices")
    op.drop_index(op.f("ix_dashboard_coach_advices_advice_key"), table_name="dashboard_coach_advices")
    op.drop_index(op.f("ix_dashboard_coach_advices_user_id"), table_name="dashboard_coach_advices")
    op.drop_table("dashboard_coach_advices")
