import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class LiftingWorkout(Base):
    __tablename__ = "lifting_workouts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lift: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_weight: Mapped[str] = mapped_column(String(64), nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_weight: Mapped[str] = mapped_column(String(64), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    date_todo: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    user = relationship("User", back_populates="lifting_workouts")
