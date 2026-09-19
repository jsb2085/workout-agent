from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.schemas.weekly_plan import (
    BodyStatsSnapshot,
    PlannedCardio,
    PlannedDay,
    PlannedGoal,
    PlannedLift,
    PlannedLocation,
    PlanningContext,
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


async def pull_context(
    *,
    week_start: date | None = None,
    week_end: date | None = None,
    store: notion.NotionStore | None = None,
) -> PlanningContext:
    start = week_start or parse_week_start(None)
    end = week_end_for(start, week_end.isoformat() if week_end else None)
    repo = store or notion.NotionStore()
    profile = await _optional(repo, "planning_context", {}) or {}
    recent_lifts = await _optional(repo, "recent_performance", [])
    this_week = await _optional_list(
        repo,
        "list_lifts",
        date_from=start.isoformat(),
        date_to=end.isoformat(),
    )
    recent_logs = await _optional_list(
        repo,
        "list_logs",
        date_from=(start - timedelta(days=14)).isoformat(),
        date_to=end.isoformat(),
    )
    return PlanningContext(
        week_start=start,
        week_end=end,
        recent_lifts=recent_lifts or [],
        this_week_lifts=this_week,
        recent_logs=recent_logs,
        goals=profile.get("goals") or [],
        locations=profile.get("locations") or [],
        default_location=profile.get("default_location"),
        latest_body_stats=profile.get("latest_body_stats"),
    )


async def _optional_list(repo, name: str, **kwargs) -> list:
    method = getattr(repo, name, None)
    if method is None:
        return []
    try:
        return await method(**kwargs)
    except notion.NotionError:
        return []


async def push_plan(
    plan: WeeklyPlan,
    *,
    dry_run: bool = False,
    include_videos: bool = True,
    store: notion.NotionStore | None = None,
) -> dict:
    if include_videos:
        plan = await attach_videos(plan)
    repo = store or notion.NotionStore()
    written: list[dict] = []
    if not dry_run:
        for day in plan.days:
            for lift in day.lifts:
                payload = {
                    "lift": lift.lift,
                    "goal_weight": lift.goal_weight,
                    "reps": lift.reps,
                    "date": day.date.isoformat(),
                    "week_start": plan.week_start.isoformat(),
                    "completed": lift.completed,
                }
                if lift.actual_weight:
                    payload["actual_weight"] = lift.actual_weight
                if lift.workout_id:
                    row = await repo.update_lift(lift.workout_id, payload)
                else:
                    row = await repo.create_lift(payload)
                    lift.workout_id = row.get("id")
                written.append(row)
            log: dict = {"date": day.date.isoformat()}
            if day.cardio:
                cardio = day.cardio[0]
                log.update(
                    {
                        "distance": cardio.distance,
                        "cardio_reps": cardio.reps,
                        "cardio_completed": cardio.completed,
                        "sprint": cardio.kind == "sprint",
                        "run": cardio.kind == "run",
                        "walk": cardio.kind == "walk",
                    }
                )
            if day.protein_goal is not None:
                log["protein_goal"] = day.protein_goal
            if day.steps_goal is not None:
                log["steps_goal"] = day.steps_goal
            if len(log) > 1:
                try:
                    await repo.upsert_log(log)
                except notion.NotionError:
                    pass
    published = await notion.publish_weekly_plan(plan, dry_run=dry_run)
    return {**published, "lifts_written": written, "lift_count": len(written)}
