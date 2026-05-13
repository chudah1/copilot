import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class ThesisEntity(Base):
    __tablename__ = "thesis_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("thesis_claims.id"), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=True)
    user_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw_extraction_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim = relationship("ThesisClaim", back_populates="entities")
    signals = relationship(
        "ThesisSignal",
        back_populates="entity",
        cascade="all, delete-orphan",
    )
