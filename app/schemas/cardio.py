import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CardioCreate(BaseModel):
    sprint: bool = False
    run: bool = False
    walk: bool = False
    distance: str
    reps: int
    completed: bool = False
    date_todo: datetime


class CardioUpdate(BaseModel):
    sprint: bool | None = None
    run: bool | None = None
    walk: bool | None = None
    distance: str | None = None
    reps: int | None = None
    completed: bool | None = None
    date_todo: datetime | None = None


class CardioRead(CardioCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
