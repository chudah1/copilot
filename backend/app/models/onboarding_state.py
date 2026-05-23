import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class OnboardingState(Base):
    __tablename__ = "onboarding_states"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    portfolio_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_reason_written_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reasons_written_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    first_digest_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day1_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day5_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reengagement_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # wizard activation tracking
    drafts_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    drafts_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wizard_skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wizard_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    investor_profile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
