import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LiftingWorkoutCreate(BaseModel):
    lift: str
    goal_weight: str
    reps: int
    actual_weight: str
    completed: bool = False
    date_todo: datetime


class LiftingWorkoutUpdate(BaseModel):
    lift: str | None = None
    goal_weight: str | None = None
    reps: int | None = None
    actual_weight: str | None = None
    completed: bool | None = None
    date_todo: datetime | None = None


class LiftingWorkoutRead(LiftingWorkoutCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
