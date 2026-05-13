"""add thesis decomposition tables

Revision ID: 20260512_add_decomposition
Revises:
Create Date: 2026-05-12 08:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260512_add_decomposition"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "thesis_decompositions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thesis_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason_type", sa.String(length=50), nullable=True),
        sa.Column("monitorability", sa.String(length=20), nullable=True),
        sa.Column("decomposition_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("raw_output_json", sa.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thesis_id", "version", name="uq_thesis_decomposition_version"),
    )
    op.create_index(op.f("ix_thesis_decompositions_thesis_id"), "thesis_decompositions", ["thesis_id"], unique=False)

    op.create_table(
        "thesis_claims",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("decomposition_id", sa.String(length=36), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("raw_extraction_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["decomposition_id"], ["thesis_decompositions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_thesis_claims_decomposition_id"), "thesis_claims", ["decomposition_id"], unique=False)

    op.create_table(
        "thesis_entities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("claim_id", sa.String(length=36), nullable=False),
        sa.Column("entity_name", sa.String(length=255), nullable=False),
        sa.Column("entity_ticker", sa.String(length=20), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("relation_type", sa.String(length=50), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), nullable=True),
        sa.Column("raw_extraction_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["thesis_claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_thesis_entities_claim_id"), "thesis_entities", ["claim_id"], unique=False)

    op.create_table(
        "thesis_signals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("signal_label", sa.String(length=255), nullable=True),
        sa.Column("signal_config_json", sa.JSON(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("raw_extraction_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["thesis_entities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_thesis_signals_entity_id"), "thesis_signals", ["entity_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_thesis_signals_entity_id"), table_name="thesis_signals")
    op.drop_table("thesis_signals")
    op.drop_index(op.f("ix_thesis_entities_claim_id"), table_name="thesis_entities")
    op.drop_table("thesis_entities")
    op.drop_index(op.f("ix_thesis_claims_decomposition_id"), table_name="thesis_claims")
    op.drop_table("thesis_claims")
    op.drop_index(op.f("ix_thesis_decompositions_thesis_id"), table_name="thesis_decompositions")
    op.drop_table("thesis_decompositions")
