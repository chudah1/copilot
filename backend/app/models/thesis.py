import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class Thesis(Base):
    __tablename__ = "theses"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    holding_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("holdings.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    thesis_kind: Mapped[str] = mapped_column(String(30), default="company")
    why_own_it: Mapped[str] = mapped_column(Text, nullable=False)
    must_remain_true: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_would_change_my_mind: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(10), default="medium")
    review_cadence_days: Mapped[int] = mapped_column(Integer, default=7)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    interpretation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_label: Mapped[str | None] = mapped_column(String(10), nullable=True)
    historical_audit_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    historical_audit_results: Mapped[list | None] = mapped_column(JSON, nullable=True)

    holding = relationship("Holding", back_populates="theses")
    user = relationship("User", back_populates="theses")
    monitoring_events = relationship("MonitoringEvent", back_populates="thesis")
    reviews = relationship(
        "ThesisReview",
        back_populates="thesis",
        cascade="all, delete-orphan",
        order_by="desc(ThesisReview.created_at)",
    )
    decompositions = relationship(
        "ThesisDecomposition",
        back_populates="thesis",
        cascade="all, delete-orphan",
        order_by="desc(ThesisDecomposition.version)",
    )
    conviction_log_entries = relationship(
        "ConvictionLogEntry",
        back_populates="thesis",
        cascade="all, delete-orphan",
        order_by="desc(ConvictionLogEntry.created_at)",
    )
    quarterly_review_responses = relationship("QuarterlyReviewResponse", back_populates="thesis")
    health_snapshots = relationship(
        "ThesisHealthSnapshot",
        back_populates="thesis",
        cascade="all, delete-orphan",
        order_by="desc(ThesisHealthSnapshot.computed_at)",
    )
    monitoring_gaps = relationship("MonitoringGap", back_populates="thesis", cascade="all, delete-orphan")
