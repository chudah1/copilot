"""add thesis reviews table

Revision ID: 20260513_add_thesis_reviews
Revises: 20260512_add_decomposition
Create Date: 2026-05-13 11:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260513_add_thesis_reviews"
down_revision = "20260512_add_decomposition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "thesis_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thesis_id", sa.String(length=36), nullable=False),
        sa.Column("monitoring_event_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["monitoring_event_id"], ["monitoring_events.id"]),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_thesis_reviews_thesis_id"), "thesis_reviews", ["thesis_id"], unique=False)
    op.create_index(
        op.f("ix_thesis_reviews_monitoring_event_id"),
        "thesis_reviews",
        ["monitoring_event_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_thesis_reviews_monitoring_event_id"), table_name="thesis_reviews")
    op.drop_index(op.f("ix_thesis_reviews_thesis_id"), table_name="thesis_reviews")
    op.drop_table("thesis_reviews")
