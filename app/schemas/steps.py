import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StepsCreate(BaseModel):
    steps_goal: int
    steps_actual: int
    date_todo: datetime


class StepsUpdate(BaseModel):
    steps_goal: int | None = None
    steps_actual: int | None = None
    date_todo: datetime | None = None


class StepsRead(StepsCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
