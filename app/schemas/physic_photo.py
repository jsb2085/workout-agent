import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PhysicPhotoUpdate(BaseModel):
    is_goal: bool | None = None
    is_current: bool | None = None
    date: datetime | None = None


class PhysicPhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    object_key: str
    is_goal: bool
    is_current: bool
    date: datetime


class PhysicPhotoUrl(BaseModel):
    url: str
    expires_in_seconds: int
