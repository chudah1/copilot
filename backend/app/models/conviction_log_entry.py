import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class ConvictionLogEntry(Base):
    __tablename__ = "conviction_log_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("theses.id"), nullable=False, index=True)
    holding_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("holdings.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thesis = relationship("Thesis", back_populates="conviction_log_entries")
    holding = relationship("Holding", back_populates="conviction_log_entries")
    user = relationship("User", back_populates="conviction_log_entries")
