from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cardio import Cardio
from app.models.lifting_workout import LiftingWorkout
from app.models.protein import Protein
from app.models.steps import Steps
from app.models.user import User
from app.schemas.weekly_plan import PlannedCardio, PlannedDay, PlannedLift, WeeklyPlan
from app.services import exercisedb, records


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_bounds(week_start: date, week_end: date | None = None) -> tuple[datetime, datetime, date]:
    end = week_end or (week_start + timedelta(days=6))
    if end < week_start:
        raise ValueError("week_end must be on or after week_start")
    start_dt = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
    return start_dt, end_dt, end


def _as_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()


def cardio_kind(item: Cardio) -> str:
    if item.sprint:
        return "sprint"
    if item.run:
        return "run"
    if item.walk:
        return "walk"
    return "cardio"


def default_title(week_start: date, week_end: date, athlete: str | None = None) -> str:
    if week_start.month == week_end.month:
        label = f"Week of {week_start:%b} {week_start.day}–{week_end.day}"
    else:
        label = f"Week of {week_start:%b} {week_start.day}–{week_end:%b} {week_end.day}"
    if athlete:
        return f"{athlete} — {label}"
    return label


async def assemble_weekly_plan(
    session: AsyncSession,
    user: User,
    *,
    week_start: date,
    week_end: date | None = None,
    focus: str | None = None,
    notes: str | None = None,
    include_videos: bool = True,
    title: str | None = None,
) -> WeeklyPlan:
    start_dt, end_dt, end = week_bounds(week_start, week_end)
    lifts = await records.list_for_user(
        session, LiftingWorkout, user.id, date_field="date_todo", date_from=start_dt, date_to=end_dt
    )
    cardios = await records.list_for_user(
        session, Cardio, user.id, date_field="date_todo", date_from=start_dt, date_to=end_dt
    )
    proteins = await records.list_for_user(
        session, Protein, user.id, date_field="date_todo", date_from=start_dt, date_to=end_dt
    )
    step_logs = await records.list_for_user(
        session, Steps, user.id, date_field="date_todo", date_from=start_dt, date_to=end_dt
    )

    videos: dict[str, Any] = {}
    if include_videos:
        videos = await exercisedb.videos_for_lift_names([item.lift for item in lifts])

    by_day: dict[date, PlannedDay] = {}
    cursor = week_start
    while cursor <= end:
        by_day[cursor] = PlannedDay(date=cursor)
        cursor += timedelta(days=1)

    for item in lifts:
        day = by_day[_as_date(item.date_todo)]
        exercise = videos.get(item.lift)
        day.lifts.append(
            PlannedLift(
                lift=item.lift,
                reps=item.reps,
                goal_weight=item.goal_weight,
                actual_weight=item.actual_weight,
                completed=item.completed,
                demo_url=exercise.demo_url if exercise else None,
                media_kind=exercise.media_kind if exercise else None,
                exercise_name=exercise.name if exercise else None,
                workout_id=str(item.id),
            )
        )
    for item in cardios:
        day = by_day[_as_date(item.date_todo)]
        day.cardio.append(
            PlannedCardio(
                kind=cardio_kind(item),
                distance=item.distance,
                reps=item.reps,
                completed=item.completed,
            )
        )
    latest_protein: dict[date, Protein] = {}
    for item in proteins:
        latest_protein[_as_date(item.date_todo)] = item
    for day_date, item in latest_protein.items():
        by_day[day_date].protein_goal = item.grams_goal
    latest_steps: dict[date, Steps] = {}
    for item in step_logs:
        latest_steps[_as_date(item.date_todo)] = item
    for day_date, item in latest_steps.items():
        by_day[day_date].steps_goal = item.steps_goal

    athlete = user.name or user.email
    return WeeklyPlan(
        week_start=week_start,
        week_end=end,
        title=title or default_title(week_start, end, athlete),
        focus=focus,
        athlete=athlete,
        notes=notes,
        days=[by_day[key] for key in sorted(by_day)],
    )


async def attach_videos(plan: WeeklyPlan) -> WeeklyPlan:
    names = [lift.lift for day in plan.days for lift in day.lifts if not lift.demo_url]
    if not names:
        return plan
    videos = await exercisedb.videos_for_lift_names(names)
    for day in plan.days:
        for lift in day.lifts:
            if lift.demo_url:
                continue
            exercise = videos.get(lift.lift)
            if exercise is None:
                continue
            lift.demo_url = exercise.demo_url
            lift.media_kind = exercise.media_kind
            lift.exercise_name = exercise.name
    return plan


def parse_week_start(value: str | None, *, today: date | None = None) -> date:
    if value:
        return date.fromisoformat(value[:10])
    return monday_of(today or datetime.now(timezone.utc).date())


async def recent_lift_performance(
    session: AsyncSession,
    user: User,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict[str, Any]]:
    """Latest actual weight per lift name, for planning the next week."""
    workouts = await records.list_for_user(
        session,
        LiftingWorkout,
        user.id,
        date_field="date_todo",
        date_from=date_from,
        date_to=date_to,
    )
    latest: dict[str, LiftingWorkout] = {}
    for item in workouts:
        key = item.lift.casefold()
        if key not in latest:
            latest[key] = item
    rows = []
    for item in latest.values():
        rows.append(
            {
                "lift": item.lift,
                "actual_weight": item.actual_weight,
                "goal_weight": item.goal_weight,
                "reps": item.reps,
                "completed": item.completed,
                "date": item.date_todo.date().isoformat(),
                "workout_id": str(item.id),
            }
        )
    rows.sort(key=lambda row: row["date"], reverse=True)
    return rows
