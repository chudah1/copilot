"""add waitlist_entries table

Revision ID: 20260527_waitlist
Revises: 20260527_thesis_health
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260527_waitlist"
down_revision = "20260527_thesis_health"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "waitlist_entries",
        sa.Column("email", sa.String(255), primary_key=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("waitlist_entries")
