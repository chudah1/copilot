import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, TZDateTime, UUIDType

DRAFT_STATUSES = ("pending", "ready", "failed", "reviewed")


class OnboardingDraft(Base):
    __tablename__ = "onboarding_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    holding_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("holdings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # pending → ready (thesis saved) or failed
    # reviewed → user confirmed / edited / dismissed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    thesis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("theses.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
