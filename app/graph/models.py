from pydantic import BaseModel, Field


class ProgressAssessment(BaseModel):
    summary: str
    priorities: list[str] = Field(default_factory=list)
    stalled_lifts: list[str] = Field(default_factory=list)
    progressing_lifts: list[str] = Field(default_factory=list)
    notes: str | None = None


class LayoutDay(BaseModel):
    date: str
    focus: str | None = None
    rest: bool = False
    lifts: list[str] = Field(default_factory=list)
    cardio_kind: str | None = None
    cardio_distance: str | None = None


class WeekLayout(BaseModel):
    focus: str
    notes: str | None = None
    days: list[LayoutDay] = Field(default_factory=list)


class LoadedLift(BaseModel):
    lift: str
    reps: int
    sets: int | None = 3
    goal_weight: str
    notes: str | None = None


class LoadedDay(BaseModel):
    date: str
    lifts: list[LoadedLift] = Field(default_factory=list)


class LoadedWeek(BaseModel):
    days: list[LoadedDay] = Field(default_factory=list)
