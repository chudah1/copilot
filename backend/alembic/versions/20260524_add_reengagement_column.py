"""add reengagement_email_sent_at to onboarding_states

Revision ID: 20260524_add_reengagement_column
Revises: 20260518_onboarding_wizard
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa

revision = "20260524_add_reengagement_column"
down_revision = "20260518_onboarding_wizard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "onboarding_states",
        sa.Column("reengagement_email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("onboarding_states", "reengagement_email_sent_at")
