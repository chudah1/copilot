import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class CoveragePass(Base):
    """One row per pipeline pass (check_now, daily monitoring_run, edgar_watch,
    historical_audit). Captures the per-source / per-stage funnel so we can
    answer Codex's "which stage failed" question instead of inferring from
    log scraping."""

    __tablename__ = "coverage_passes"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("theses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    holding_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False)
    run_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    triggered_by: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
