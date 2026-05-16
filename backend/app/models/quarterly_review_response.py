import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class QuarterlyReviewResponse(Base):
    __tablename__ = "quarterly_review_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("quarterly_reviews.id"), nullable=False, index=True
    )
    holding_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("holdings.id"), nullable=False, index=True)
    thesis_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("theses.id"), nullable=False, index=True)
    response: Mapped[str] = mapped_column(String(20), nullable=False)
    price_at_review: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    review = relationship("QuarterlyReview", back_populates="responses")
    holding = relationship("Holding", back_populates="quarterly_review_responses")
    thesis = relationship("Thesis", back_populates="quarterly_review_responses")
