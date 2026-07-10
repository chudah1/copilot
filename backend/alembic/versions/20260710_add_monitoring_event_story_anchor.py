"""Add story_anchor to monitoring_events

Revision ID: 20260710_monitoring_event_story_anchor
Revises: 20260705_investor_profile
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260710_monitoring_event_story_anchor"
down_revision = "20260705_investor_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "monitoring_events",
        sa.Column("story_anchor", sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column("monitoring_events", "story_anchor")
