import uuid

from pydantic import BaseModel, ConfigDict


class GymLocationCreate(BaseModel):
    location_name: str
    description: str


class GymLocationUpdate(BaseModel):
    location_name: str | None = None
    description: str | None = None


class GymLocationRead(GymLocationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
