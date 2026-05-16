import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class QuarterlyReview(Base):
    __tablename__ = "quarterly_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)
    quarter: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="quarterly_reviews")
    responses = relationship(
        "QuarterlyReviewResponse",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="desc(QuarterlyReviewResponse.created_at)",
    )
