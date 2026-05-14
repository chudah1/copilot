import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class ThesisReview(Base):
    __tablename__ = "thesis_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("theses.id"), nullable=False, index=True)
    monitoring_event_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("monitoring_events.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thesis = relationship("Thesis", back_populates="reviews")
    monitoring_event = relationship("MonitoringEvent", back_populates="reviews")
