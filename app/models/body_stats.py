import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BodyStats(Base):
    __tablename__ = "body_stats"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    height: Mapped[str] = mapped_column(String(64), nullable=False)
    weight: Mapped[str] = mapped_column(String(64), nullable=False)
    squat: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bench: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deadlift: Mapped[str | None] = mapped_column(String(64), nullable=True)
    overhead_press: Mapped[str | None] = mapped_column(String(64), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    user = relationship("User", back_populates="body_stats")
