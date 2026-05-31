import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("broker_connections.id"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(precision=18, scale=8), nullable=False)
    average_cost_basis: Mapped[float] = mapped_column(Numeric(precision=18, scale=4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    current_price: Mapped[float | None] = mapped_column(Numeric(precision=18, scale=4), nullable=True)
    current_value: Mapped[float | None] = mapped_column(Numeric(precision=18, scale=4), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geography: Mapped[str | None] = mapped_column(String(100), nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # When monitoring last ran for this holding (price/news/filing pass), set even
    # when the pass is quiet and creates no event — so the dashboard can truthfully
    # show "checked X ago" instead of an unverified "all calm".
    last_monitored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="holdings")
    broker_connection = relationship("BrokerConnection", back_populates="holdings")
    theses = relationship("Thesis", back_populates="holding")
    monitoring_events = relationship("MonitoringEvent", back_populates="holding")
    conviction_log_entries = relationship("ConvictionLogEntry", back_populates="holding")
    notifications = relationship("UserNotification", back_populates="holding")
    quarterly_review_responses = relationship("QuarterlyReviewResponse", back_populates="holding")
