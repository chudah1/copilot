import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class ClaimReview(Base):
    """One verdict on one claim from a thesis check-in.

    A claim's current state is its latest row; a claim with no rows holds by
    default. claim_id is null for the thesis-level "general evidence" bucket
    (events that bind to no claim) and for theses without a decomposition.
    Rows written in the same sitting share a session_id.
    """

    __tablename__ = "claim_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType, ForeignKey("theses.id"), nullable=False, index=True
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType, ForeignKey("thesis_claims.id"), nullable=True, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # holds | weakened | broken
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thesis = relationship("Thesis")
    claim = relationship("ThesisClaim")
