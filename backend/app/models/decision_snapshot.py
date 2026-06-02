import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class DecisionSnapshot(Base):
    """A point-in-time capture of a conviction decision (a verdict on a fired
    monitoring event, or a periodic re-underwrite) plus the state of what the user
    was betting on, so the outcome can be read back later.

    This is the capture half of the decision-mirror loop: written synchronously
    from values already in hand at decision time (no network fetch). The resolution
    fields are reserved (left null) and filled later by an earnings-anchored job.
    """

    __tablename__ = "decision_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)
    thesis_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("theses.id"), nullable=False, index=True)
    holding_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("holdings.id"), nullable=False, index=True)
    monitoring_event_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    claim_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True, index=True)

    # The decision. verdict is the raw 5-value review action; bucket is the
    # display grouping (held / exited / dismissed).
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    bucket: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    decision_source: Mapped[str] = mapped_column(String(30), nullable=False, default="event_review")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Price context at decision (native per-share + GBP value). Benchmark is a
    # ticker only; its price is reconstructed historically at resolution time.
    price_native: Mapped[float | None] = mapped_column(Numeric(precision=18, scale=4), nullable=True)
    value_gbp: Mapped[float | None] = mapped_column(Numeric(precision=18, scale=4), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    benchmark_ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # When the bet next gets tested (next earnings); null -> 90-day soft read.
    next_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # What the user held through / dismissed, and the condition state at decision
    # (watch hints + triggering evidence) so the reasoning mirror can re-read it.
    bet_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Reserved for the resolution half (filled later, not at capture).
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
