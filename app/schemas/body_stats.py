import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BodyStatsCreate(BaseModel):
    height: str
    weight: str
    squat: str | None = Field(
        default=None,
        description="Current squat. Omit or send null for I don't know.",
    )
    bench: str | None = Field(
        default=None,
        description="Current bench press. Omit or send null for I don't know.",
    )
    deadlift: str | None = Field(
        default=None,
        description="Current deadlift. Omit or send null for I don't know.",
    )
    overhead_press: str | None = Field(
        default=None,
        description="Current overhead press. Omit or send null for I don't know.",
    )
    date: datetime


class BodyStatsUpdate(BaseModel):
    height: str | None = None
    weight: str | None = None
    squat: str | None = None
    bench: str | None = None
    deadlift: str | None = None
    overhead_press: str | None = None
    date: datetime | None = None


class BodyStatsRead(BodyStatsCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
