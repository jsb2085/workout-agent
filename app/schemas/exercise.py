from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExerciseVideo(BaseModel):
    """Normalized ExerciseDB exercise with demonstration media."""

    model_config = ConfigDict(extra="ignore")

    exercise_id: str
    name: str
    video_url: str | None = None
    gif_url: str | None = None
    image_url: str | None = None
    demo_url: str | None = None
    media_kind: str | None = None
    body_parts: list[str] = Field(default_factory=list)
    target_muscles: list[str] = Field(default_factory=list)
    secondary_muscles: list[str] = Field(default_factory=list)
    equipments: list[str] = Field(default_factory=list)
    exercise_type: str | None = None
    instructions: list[str] = Field(default_factory=list)
    overview: str | None = None
    exercise_tips: list[str] = Field(default_factory=list)
    variations: list[str] = Field(default_factory=list)
    match_score: int | None = None


class ExerciseSearchResponse(BaseModel):
    source: str
    total: int | None = None
    exercises: list[ExerciseVideo]


class WorkoutExerciseVideo(BaseModel):
    workout_id: UUID
    lift: str
    query: str
    workout: dict[str, Any]
    exercise: ExerciseVideo | None = None


class WorkoutExerciseVideosResponse(BaseModel):
    source: str
    workouts: list[WorkoutExerciseVideo]
    unmatched: list[str] = Field(default_factory=list)
