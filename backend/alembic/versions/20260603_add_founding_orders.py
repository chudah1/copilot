"""add founding_orders table (presale)

Revision ID: 20260603_founding
Revises: 20260602_decision_snapshots
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "20260603_founding"
down_revision = "20260602_decision_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "founding_orders",
        sa.Column("stripe_session_id", sa.String(255), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_founding_orders_status", "founding_orders", ["status"])
    op.create_index("ix_founding_orders_email", "founding_orders", ["email"])


def downgrade():
    op.drop_index("ix_founding_orders_email", table_name="founding_orders")
    op.drop_index("ix_founding_orders_status", table_name="founding_orders")
    op.drop_table("founding_orders")
