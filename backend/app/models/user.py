import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    preferences: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {"digest_frequency": "weekly", "notification_sensitivity": "all"},
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    broker_connections = relationship("BrokerConnection", back_populates="user")
    holdings = relationship("Holding", back_populates="user")
    theses = relationship("Thesis", back_populates="user")
    digests = relationship("Digest", back_populates="user")
