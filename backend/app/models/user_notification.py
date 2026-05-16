import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    holding_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, ForeignKey("holdings.id"), nullable=True)
    thesis_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")
    holding = relationship("Holding", back_populates="notifications")
