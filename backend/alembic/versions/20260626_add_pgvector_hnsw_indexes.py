"""add pgvector hnsw indexes for embeddings

Revision ID: 20260626_pgvector_hnsw
Revises: 20260623_add_embedding_storage
Create Date: 2026-06-26
"""

from alembic import op


revision = "20260626_pgvector_hnsw"
down_revision = "20260623_add_embedding_storage"
branch_labels = None
depends_on = None


_EVIDENCE_CHUNKS_HNSW_INDEX = """
CREATE INDEX IF NOT EXISTS ix_evidence_chunks_embedding_hnsw
ON evidence_chunks
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL
"""

_THESIS_CLAIMS_HNSW_INDEX = """
CREATE INDEX IF NOT EXISTS ix_thesis_claims_embedding_hnsw
ON thesis_claims
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL
"""


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(_EVIDENCE_CHUNKS_HNSW_INDEX)
    op.execute(_THESIS_CLAIMS_HNSW_INDEX)


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_thesis_claims_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_evidence_chunks_embedding_hnsw")
