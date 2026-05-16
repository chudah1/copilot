"""add quarterly review tables

Revision ID: 20260516_quarterly_review
Revises: 20260516_noise_suppression
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa

from app.database import UUIDType


revision = "20260516_quarterly_review"
down_revision = "20260516_noise_suppression"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quarterly_reviews",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("user_id", UUIDType(), nullable=False),
        sa.Column("quarter", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quarterly_reviews_user_id"), "quarterly_reviews", ["user_id"], unique=False)
    op.create_index(op.f("ix_quarterly_reviews_quarter"), "quarterly_reviews", ["quarter"], unique=False)

    op.create_table(
        "quarterly_review_responses",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("review_id", UUIDType(), nullable=False),
        sa.Column("holding_id", UUIDType(), nullable=False),
        sa.Column("thesis_id", UUIDType(), nullable=False),
        sa.Column("response", sa.String(length=20), nullable=False),
        sa.Column("price_at_review", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["holding_id"], ["holdings.id"]),
        sa.ForeignKeyConstraint(["review_id"], ["quarterly_reviews.id"]),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quarterly_review_responses_review_id"),
        "quarterly_review_responses",
        ["review_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quarterly_review_responses_holding_id"),
        "quarterly_review_responses",
        ["holding_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quarterly_review_responses_thesis_id"),
        "quarterly_review_responses",
        ["thesis_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quarterly_review_responses_thesis_id"), table_name="quarterly_review_responses")
    op.drop_index(op.f("ix_quarterly_review_responses_holding_id"), table_name="quarterly_review_responses")
    op.drop_index(op.f("ix_quarterly_review_responses_review_id"), table_name="quarterly_review_responses")
    op.drop_table("quarterly_review_responses")
    op.drop_index(op.f("ix_quarterly_reviews_quarter"), table_name="quarterly_reviews")
    op.drop_index(op.f("ix_quarterly_reviews_user_id"), table_name="quarterly_reviews")
    op.drop_table("quarterly_reviews")
