import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class EarningsCalendar(Base):
    __tablename__ = "earnings_calendar"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    report_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="yfinance")
    last_refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
