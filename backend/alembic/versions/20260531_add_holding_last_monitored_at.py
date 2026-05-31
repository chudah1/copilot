"""add holdings.last_monitored_at

Records when monitoring last ran for a holding (even on a quiet pass that creates
no event), so the dashboard can truthfully show "checked X ago".

Revision ID: 20260531_last_monitored
Revises: 20260527_health_snapshots
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "20260531_last_monitored"
down_revision = "20260527_health_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "holdings",
        sa.Column("last_monitored_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("holdings", "last_monitored_at")
