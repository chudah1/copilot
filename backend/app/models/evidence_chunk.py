import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, EmbeddingType, UUIDType


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("theses.id"), nullable=True, index=True
    )
    holding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("holdings.id"), nullable=True, index=True
    )
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType(), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
