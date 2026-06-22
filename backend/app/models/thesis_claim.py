import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, EmbeddingType, UUIDType


class ThesisClaim(Base):
    __tablename__ = "thesis_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    decomposition_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("thesis_decompositions.id"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_extraction_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType(), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    decomposition = relationship("ThesisDecomposition", back_populates="claims")
    entities = relationship(
        "ThesisEntity",
        back_populates="claim",
        cascade="all, delete-orphan",
    )
