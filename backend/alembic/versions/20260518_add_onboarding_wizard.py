"""Add onboarding wizard fields and onboarding_drafts table

Revision ID: 20260518_onboarding_wizard
Revises: 20260516_onboarding_state, 20260516_quarterly_review
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

from app.database import UUIDType

revision = "20260518_onboarding_wizard"
down_revision = ("20260516_onboarding_state", "20260516_quarterly_review")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend onboarding_states with wizard tracking columns
    op.add_column("onboarding_states", sa.Column("drafts_generated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("onboarding_states", sa.Column("drafts_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("onboarding_states", sa.Column("wizard_skipped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("onboarding_states", sa.Column("wizard_completed_at", sa.DateTime(timezone=True), nullable=True))

    # New onboarding_drafts table
    op.create_table(
        "onboarding_drafts",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("user_id", UUIDType(), nullable=False),
        sa.Column("holding_id", UUIDType(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("thesis_id", UUIDType(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["holding_id"], ["holdings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_onboarding_drafts_user_id", "onboarding_drafts", ["user_id"])
    op.create_index("ix_onboarding_drafts_holding_id", "onboarding_drafts", ["holding_id"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_drafts_holding_id", table_name="onboarding_drafts")
    op.drop_index("ix_onboarding_drafts_user_id", table_name="onboarding_drafts")
    op.drop_table("onboarding_drafts")
    op.drop_column("onboarding_states", "wizard_completed_at")
    op.drop_column("onboarding_states", "wizard_skipped_at")
    op.drop_column("onboarding_states", "drafts_reviewed_at")
    op.drop_column("onboarding_states", "drafts_generated_at")
