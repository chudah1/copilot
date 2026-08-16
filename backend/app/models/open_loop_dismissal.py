import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base, TZDateTime, UUIDType


class OpenLoopDismissal(Base):
    __tablename__ = "open_loop_dismissals"
    __table_args__ = (
        UniqueConstraint("user_id", "loop_key", name="uq_open_loop_dismissals_user_loop_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)
    loop_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dismissed_until: Mapped[datetime] = mapped_column(TZDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())

    user = relationship("User", back_populates="open_loop_dismissals")
