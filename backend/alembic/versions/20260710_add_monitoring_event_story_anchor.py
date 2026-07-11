"""Add story_anchor to monitoring_events

Revision ID: 20260710_story_anchor
Revises: 20260705_investor_profile
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa


# Shortened to stay under Alembic's default 32-char alembic_version.version_num
# limit; the previous 38-char id ("20260710_monitoring_event_story_anchor")
# ran the DDL then crashed on the version bump, leaving prod's schema ahead
# of its recorded version. We use an idempotent add_column below so a redeploy
# re-tries safely.
revision = "20260710_story_anchor"
down_revision = "20260705_investor_profile"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("monitoring_events")}
    if "story_anchor" not in existing:
        op.add_column(
            "monitoring_events",
            sa.Column("story_anchor", sa.String(length=255), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("monitoring_events")}
    if "story_anchor" in existing:
        op.drop_column("monitoring_events", "story_anchor")
