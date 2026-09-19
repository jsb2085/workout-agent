from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from app.graph.llm import complete_structured
from app.graph.models import LoadedWeek, ProgressAssessment, WeekLayout
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
from app.services.weekly_plan import default_title, week_end_for

_PROGRESS_SYSTEM = """You are a strength coach reviewing one athlete.
Compare their active goals to recent lift Actual weights, body stats, and logs.
Be specific about what is moving, what is stalled, and what this week should emphasize.
Do not invent lifts or numbers that are not in the data."""

_LAYOUT_SYSTEM = """You are a strength coach writing this week's session menu.
Use the progress notes and the default workout location's equipment.
Cover week_start through week_end. Include rest days. Typically 3-5 lifting days.
Only prescribe lifts that fit the listed equipment. If equipment is unknown, stick to basics
(squat, hinge, press, pull, carry) and say so in notes.
Do not assign reps or weights yet. cardio_kind must be sprint, run, walk, or empty."""

_LOADS_SYSTEM = """You are a strength coach assigning sets, reps, and goal weights.
Use recent Actual weight when present, else Goal weight, else body-stat lift numbers.
Progress small (about 0-5 lb or a rep) unless the lift is stalled — then hold or deload slightly.
Leave Actual weight blank. Never exceed a goal that is far above last actual in one week.
Match the lift names and dates from the week layout. Skip rest days."""


def _dump(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, indent=2, default=str)


async def assess_progress(context: PlanningContext, complete=complete_structured) -> ProgressAssessment:
    user = (
        "Active goals, recent lifts (Actual weight is what they actually did), "
        "body stats, and recent logs:\n"
        f"{_dump(context)}"
    )
    return await complete(ProgressAssessment, _PROGRESS_SYSTEM, user)


async def plan_sessions(
    context: PlanningContext,
    progress: ProgressAssessment,
    complete=complete_structured,
) -> WeekLayout:
    user = (
        f"Week {context.week_start} to {week_end_for(context.week_start)}.\n"
        f"Default location: {_dump(context.default_location)}\n"
        f"All locations: {_dump(context.locations)}\n"
        f"Progress assessment:\n{_dump(progress)}\n"
        f"Recent lifts:\n{_dump(context.recent_lifts)}"
    )
    return await complete(WeekLayout, _LAYOUT_SYSTEM, user)


async def assign_loads(
    context: PlanningContext,
    progress: ProgressAssessment,
    layout: WeekLayout,
    complete=complete_structured,
) -> LoadedWeek:
    user = (
        f"Progress:\n{_dump(progress)}\n"
        f"Week layout:\n{_dump(layout)}\n"
        f"Recent lifts (use Actual weight first):\n{_dump(context.recent_lifts)}\n"
        f"Body stats:\n{_dump(context.latest_body_stats)}"
    )
    return await complete(LoadedWeek, _LOADS_SYSTEM, user)


def _models(model, rows: list) -> list:
    parsed = []
    for row in rows:
        try:
            item = model.model_validate(row)
        except Exception:
            continue
        if getattr(item, "name", None) == "":
            continue
        parsed.append(item)
    return parsed


def assemble_plan(
    context: PlanningContext,
    progress: ProgressAssessment,
    layout: WeekLayout,
    loaded: LoadedWeek,
) -> WeeklyPlan:
    end = week_end_for(context.week_start)
    by_date: dict[str, PlannedDay] = {}
    cursor = context.week_start
    while cursor <= end:
        by_date[cursor.isoformat()] = PlannedDay(date=cursor)
        cursor += timedelta(days=1)

    loads = {day.date[:10]: day for day in loaded.days}
    for day in layout.days:
        key = day.date[:10]
        if key not in by_date:
            try:
                parsed = date.fromisoformat(key)
            except ValueError:
                continue
            if parsed < context.week_start or parsed > end:
                continue
            by_date[key] = PlannedDay(date=parsed)
        planned = by_date[key]
        planned.focus = day.focus
        if day.rest:
            planned.notes = planned.notes or "Rest"
            continue
        loaded_day = loads.get(key)
        weight_by_name = {item.lift.casefold(): item for item in (loaded_day.lifts if loaded_day else [])}
        for name in day.lifts:
            item = weight_by_name.get(name.casefold())
            planned.lifts.append(
                PlannedLift(
                    lift=name,
                    reps=item.reps if item else None,
                    sets=item.sets if item else None,
                    goal_weight=item.goal_weight if item else None,
                    notes=item.notes if item else None,
                )
            )
        if day.cardio_kind:
            planned.cardio.append(PlannedCardio(kind=day.cardio_kind, distance=day.cardio_distance))

    notes = " | ".join(part for part in (progress.summary, layout.notes) if part)
    body_stats = None
    if context.latest_body_stats:
        try:
            body_stats = BodyStatsSnapshot.model_validate(context.latest_body_stats)
        except Exception:
            body_stats = None
    return WeeklyPlan(
        week_start=context.week_start,
        week_end=end,
        title=default_title(context.week_start, end),
        focus=layout.focus or (progress.priorities[0] if progress.priorities else None),
        notes=notes or None,
        days=[by_date[key] for key in sorted(by_date)],
        goals=_models(PlannedGoal, context.goals),
        locations=_models(PlannedLocation, context.locations),
        body_stats=body_stats,
    )
