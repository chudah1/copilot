"""Add claim reviews table

Revision ID: 20260715_claim_reviews
Revises: 20260713_soak_reports
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "20260715_claim_reviews"
down_revision = "20260713_soak_reports"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "claim_reviews" in existing_tables:
        return

    op.create_table(
        "claim_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thesis_id", sa.String(length=36), sa.ForeignKey("theses.id"), nullable=False),
        sa.Column("claim_id", sa.String(length=36), sa.ForeignKey("thesis_claims.id"), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claim_reviews_thesis_id", "claim_reviews", ["thesis_id"], unique=False)
    op.create_index("ix_claim_reviews_claim_id", "claim_reviews", ["claim_id"], unique=False)
    op.create_index("ix_claim_reviews_session_id", "claim_reviews", ["session_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "claim_reviews" not in existing_tables:
        return
    indexes = {index["name"] for index in inspector.get_indexes("claim_reviews")}
    for name in ("ix_claim_reviews_thesis_id", "ix_claim_reviews_claim_id", "ix_claim_reviews_session_id"):
        if name in indexes:
            op.drop_index(name, table_name="claim_reviews")
    op.drop_table("claim_reviews")
