import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    lifting_workouts = relationship("LiftingWorkout", back_populates="user", cascade="all, delete-orphan")
    cardios = relationship("Cardio", back_populates="user", cascade="all, delete-orphan")
    gym_locations = relationship("GymLocation", back_populates="user", cascade="all, delete-orphan")
    performance_goals = relationship("PerformanceGoal", back_populates="user", cascade="all, delete-orphan")
    physic_photos = relationship("PhysicPhoto", back_populates="user", cascade="all, delete-orphan")
    proteins = relationship("Protein", back_populates="user", cascade="all, delete-orphan")
    steps = relationship("Steps", back_populates="user", cascade="all, delete-orphan")
