import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_user_snapshot_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    total_cost: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    top_3_concentration_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    thesis_coverage_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    monitorable_pct: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    unmonitored_count: Mapped[int] = mapped_column(Integer, nullable=False)
    holdings_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
