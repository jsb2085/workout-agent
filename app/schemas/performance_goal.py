import uuid

from pydantic import BaseModel, ConfigDict


class PerformanceGoalCreate(BaseModel):
    goal_name: str
    description: str


class PerformanceGoalUpdate(BaseModel):
    goal_name: str | None = None
    description: str | None = None


class PerformanceGoalRead(PerformanceGoalCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
