import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class ThesisDecomposition(Base):
    __tablename__ = "thesis_decompositions"
    __table_args__ = (
        UniqueConstraint("thesis_id", "version", name="uq_thesis_decomposition_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("theses.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    reason_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    monitorability: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decomposition_confidence: Mapped[float | None] = mapped_column(Numeric(precision=5, scale=4), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thesis = relationship("Thesis", back_populates="decompositions")
    claims = relationship(
        "ThesisClaim",
        back_populates="decomposition",
        cascade="all, delete-orphan",
        order_by="ThesisClaim.position",
    )
