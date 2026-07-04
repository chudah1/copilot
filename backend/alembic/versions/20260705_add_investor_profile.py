"""Add investor_profile to onboarding_states

Revision ID: 20260705_investor_profile
Revises: 20260626_pgvector_hnsw
Create Date: 2026-07-05

The column exists in the model (onboarding_state.py) and was silently masked
in local SQLite by sqlite_dev_compat, but was never added to Postgres. Any
insert/select touching onboarding_states crashes in production until this runs.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260705_investor_profile"
down_revision = "20260626_pgvector_hnsw"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "onboarding_states",
        sa.Column("investor_profile", sa.String(length=32), nullable=True),
    )


def downgrade():
    op.drop_column("onboarding_states", "investor_profile")
