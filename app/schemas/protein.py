import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProteinCreate(BaseModel):
    grams_goal: int
    grams_actual: int
    date_todo: datetime


class ProteinUpdate(BaseModel):
    grams_goal: int | None = None
    grams_actual: int | None = None
    date_todo: datetime | None = None


class ProteinRead(ProteinCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
