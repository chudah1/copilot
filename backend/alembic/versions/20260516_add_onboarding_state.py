"""add onboarding_states table

Revision ID: 20260516_onboarding_state
Revises: 20260516_earnings_notifications
Create Date: 2026-05-16
"""

revision = "20260516_onboarding_state"
down_revision = "20260516_earnings_notifications"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.create_table(
        "onboarding_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_reason_written_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reasons_written_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_digest_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("day1_email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("day5_email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_onboarding_states_user_id", "onboarding_states", ["user_id"])


def downgrade():
    op.drop_index("ix_onboarding_states_user_id", table_name="onboarding_states")
    op.drop_table("onboarding_states")
