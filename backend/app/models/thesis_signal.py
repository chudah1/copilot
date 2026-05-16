import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class ThesisSignal(Base):
    __tablename__ = "thesis_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("thesis_entities.id"), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    signal_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signal_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=True)
    user_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_extraction_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_ignores: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entity = relationship("ThesisEntity", back_populates="signals")
