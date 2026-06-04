"""add founding_reservations table (no-charge presale intent)

Revision ID: 20260603_reservations
Revises: 20260603_founding
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "20260603_reservations"
down_revision = "20260603_founding"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "founding_reservations",
        sa.Column("email", sa.String(255), primary_key=True),
        sa.Column("tier", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("founding_reservations")
