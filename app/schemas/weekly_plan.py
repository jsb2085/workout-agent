from datetime import date

from pydantic import BaseModel, Field


class PlannedLift(BaseModel):
    lift: str
    reps: int | None = None
    sets: int | None = None
    goal_weight: str | None = None
    actual_weight: str | None = None
    completed: bool = False
    notes: str | None = None
    demo_url: str | None = None
    media_kind: str | None = None
    exercise_name: str | None = None
    workout_id: str | None = None


class PlannedCardio(BaseModel):
    kind: str
    distance: str | None = None
    reps: int | None = None
    completed: bool = False


class PlannedDay(BaseModel):
    date: date
    focus: str | None = None
    lifts: list[PlannedLift] = Field(default_factory=list)
    cardio: list[PlannedCardio] = Field(default_factory=list)
    protein_goal: int | None = None
    steps_goal: int | None = None
    notes: str | None = None


class PlannedGoal(BaseModel):
    name: str
    target: str | None = None
    metric: str | None = None
    deadline: str | None = None
    status: str | None = None
    description: str | None = None


class PlannedLocation(BaseModel):
    name: str
    description: str | None = None
    equipment: str | None = None
    is_default: bool = False


class BodyStatsSnapshot(BaseModel):
    date: date | None = None
    height: str | None = None
    weight: str | None = None
    squat: str | None = None
    bench: str | None = None
    deadlift: str | None = None
    overhead_press: str | None = None


class WeeklyPlan(BaseModel):
    week_start: date
    week_end: date
    title: str
    focus: str | None = None
    notes: str | None = None
    days: list[PlannedDay] = Field(default_factory=list)
    goals: list[PlannedGoal] = Field(default_factory=list)
    locations: list[PlannedLocation] = Field(default_factory=list)
    body_stats: BodyStatsSnapshot | None = None
