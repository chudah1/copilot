import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class DashboardCoachAdvice(Base):
    __tablename__ = "dashboard_coach_advices"
    __table_args__ = (
        UniqueConstraint("user_id", "advice_key", name="uq_dashboard_coach_advices_user_advice"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)
    advice_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    holding_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, ForeignKey("holdings.id"), nullable=True, index=True)
    thesis_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, ForeignKey("theses.id"), nullable=True, index=True)
    decision_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, ForeignKey("decision_snapshots.id"), nullable=True, index=True)
    loop_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    pattern_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="presented", index=True)
    presented_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    first_presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_action_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)  # helped | hurt

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
