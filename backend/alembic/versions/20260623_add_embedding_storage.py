"""add embedding storage for claims and evidence chunks

Revision ID: 20260623_add_embedding_storage
Revises: 20260608_add_historical_audit
Create Date: 2026-06-23
"""

from alembic import op
import sqlalchemy as sa

from app.database import EmbeddingType, UUIDType

revision = "20260623_add_embedding_storage"
down_revision = "20260608_add_historical_audit"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column("thesis_claims", sa.Column("embedding_text", sa.Text(), nullable=True))
    op.add_column("thesis_claims", sa.Column("embedding", EmbeddingType(), nullable=True))
    op.add_column("thesis_claims", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "evidence_chunks",
        sa.Column("id", UUIDType(), nullable=False),
        sa.Column("thesis_id", UUIDType(), nullable=True),
        sa.Column("holding_id", UUIDType(), nullable=True),
        sa.Column("ticker", sa.String(length=20), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("chunk_type", sa.String(length=50), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("embedding", EmbeddingType(), nullable=True),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["holding_id"], ["holdings.id"]),
        sa.ForeignKeyConstraint(["thesis_id"], ["theses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidence_chunks_holding_id"), "evidence_chunks", ["holding_id"], unique=False)
    op.create_index(op.f("ix_evidence_chunks_source_id"), "evidence_chunks", ["source_id"], unique=False)
    op.create_index(op.f("ix_evidence_chunks_source_type"), "evidence_chunks", ["source_type"], unique=False)
    op.create_index(op.f("ix_evidence_chunks_thesis_id"), "evidence_chunks", ["thesis_id"], unique=False)
    op.create_index(op.f("ix_evidence_chunks_ticker"), "evidence_chunks", ["ticker"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_evidence_chunks_ticker"), table_name="evidence_chunks")
    op.drop_index(op.f("ix_evidence_chunks_thesis_id"), table_name="evidence_chunks")
    op.drop_index(op.f("ix_evidence_chunks_source_type"), table_name="evidence_chunks")
    op.drop_index(op.f("ix_evidence_chunks_source_id"), table_name="evidence_chunks")
    op.drop_index(op.f("ix_evidence_chunks_holding_id"), table_name="evidence_chunks")
    op.drop_table("evidence_chunks")

    op.drop_column("thesis_claims", "embedded_at")
    op.drop_column("thesis_claims", "embedding")
    op.drop_column("thesis_claims", "embedding_text")
