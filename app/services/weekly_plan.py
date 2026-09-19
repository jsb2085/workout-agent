from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.schemas.weekly_plan import (
    BodyStatsSnapshot,
    PlannedCardio,
    PlannedDay,
    PlannedGoal,
    PlannedLift,
    PlannedLocation,
    WeeklyPlan,
)
from app.services import exercisedb, notion


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def parse_week_start(value: str | None, *, today: date | None = None) -> date:
    if value:
        return date.fromisoformat(value[:10])
    return monday_of(today or datetime.now(timezone.utc).date())


def week_end_for(week_start: date, week_end: str | None = None) -> date:
    if week_end:
        end = date.fromisoformat(week_end[:10])
        if end < week_start:
            raise ValueError("week_end must be on or after week_start")
        return end
    return week_start + timedelta(days=6)


def default_title(week_start: date, week_end: date) -> str:
    if week_start.month == week_end.month:
        return f"Week of {week_start:%b} {week_start.day}–{week_end.day}"
    return f"Week of {week_start:%b} {week_start.day}–{week_end:%b} {week_end.day}"


async def assemble_weekly_plan(
    *,
    week_start: date,
    week_end: date | None = None,
    focus: str | None = None,
    notes: str | None = None,
    title: str | None = None,
    include_videos: bool = True,
    store: notion.NotionStore | None = None,
) -> WeeklyPlan:
    end = week_end or week_end_for(week_start)
    repo = store or notion.NotionStore()
    lifts = await repo.list_lifts(
        date_from=week_start.isoformat(),
        date_to=end.isoformat(),
    )
    logs: list[dict] = []
    try:
        logs = await repo.list_logs(
            date_from=week_start.isoformat(),
            date_to=end.isoformat(),
        )
    except notion.NotionError:
        logs = []

    videos: dict = {}
    if include_videos:
        videos = await exercisedb.videos_for_lift_names([row["lift"] for row in lifts if row.get("lift")])

    by_day: dict[date, PlannedDay] = {}
    cursor = week_start
    while cursor <= end:
        by_day[cursor] = PlannedDay(date=cursor)
        cursor += timedelta(days=1)

    for row in lifts:
        if not row.get("date"):
            continue
        day_key = date.fromisoformat(row["date"][:10])
        if day_key not in by_day:
            continue
        day = by_day[day_key]
        exercise = videos.get(row["lift"]) if row.get("lift") else None
        day.lifts.append(
            PlannedLift(
                lift=row.get("lift") or "",
                reps=row.get("reps"),
                goal_weight=row.get("goal_weight"),
                actual_weight=row.get("actual_weight"),
                completed=bool(row.get("completed")),
                demo_url=exercise.demo_url if exercise else None,
                media_kind=exercise.media_kind if exercise else None,
                exercise_name=exercise.name if exercise else None,
                workout_id=row.get("id"),
            )
        )
    for row in logs:
        if not row.get("date"):
            continue
        day_key = date.fromisoformat(row["date"][:10])
        if day_key not in by_day:
            continue
        day = by_day[day_key]
        if row.get("cardio_kind"):
            day.cardio.append(
                PlannedCardio(
                    kind=row["cardio_kind"],
                    distance=row.get("distance"),
                    reps=row.get("cardio_reps"),
                    completed=bool(row.get("cardio_completed")),
                )
            )
        day.protein_goal = row.get("protein_goal")
        day.steps_goal = row.get("steps_goal")

    context = await _planning_context(repo)
    return WeeklyPlan(
        week_start=week_start,
        week_end=end,
        title=title or default_title(week_start, end),
        focus=focus,
        notes=notes,
        days=[by_day[key] for key in sorted(by_day)],
        goals=context["goals"],
        locations=context["locations"],
        body_stats=context["body_stats"],
    )


async def _optional(repo, name: str, default):
    method = getattr(repo, name, None)
    if method is None:
        return default
    try:
        return await method()
    except notion.NotionError:
        return default


async def _planning_context(repo) -> dict:
    raw_goals = await _optional(repo, "list_goals", [])
    raw_locations = await _optional(repo, "list_locations", [])
    raw_stats = await _optional(repo, "list_body_stats", [])
    goals = []
    for row in raw_goals:
        if (row.get("status") or "Active").casefold() in {"done", "complete", "completed"}:
            continue
        if not row.get("name"):
            continue
        goals.append(
            PlannedGoal(
                name=row["name"],
                target=row.get("target"),
                metric=row.get("metric"),
                deadline=row.get("deadline"),
                status=row.get("status"),
                description=row.get("description"),
            )
        )
    locations = [
        PlannedLocation(
            name=row.get("name") or "",
            description=row.get("description"),
            equipment=row.get("equipment"),
            is_default=bool(row.get("is_default")),
        )
        for row in raw_locations
        if row.get("name")
    ]
    latest = raw_stats[0] if raw_stats else None
    body_stats = None
    if latest:
        body_stats = BodyStatsSnapshot(
            date=date.fromisoformat(latest["date"][:10]) if latest.get("date") else None,
            height=latest.get("height"),
            weight=latest.get("weight"),
            squat=latest.get("squat"),
            bench=latest.get("bench"),
            deadlift=latest.get("deadlift"),
            overhead_press=latest.get("overhead_press"),
        )
    return {"goals": goals, "locations": locations, "body_stats": body_stats}


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
