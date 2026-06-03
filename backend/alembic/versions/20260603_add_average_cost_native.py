"""add holdings.average_cost_native (per-share cost in the instrument's native currency)

Revision ID: 20260603_avg_cost_native
Revises: 20260603_reservations
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "20260603_avg_cost_native"
down_revision = "20260603_reservations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "holdings",
        sa.Column("average_cost_native", sa.Numeric(precision=18, scale=4), nullable=True),
    )


def downgrade():
    op.drop_column("holdings", "average_cost_native")
