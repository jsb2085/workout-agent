from __future__ import annotations

import json
from datetime import date
from typing import Any

from fastmcp import FastMCP

from app.schemas.weekly_plan import WeeklyPlan
from app.services import exercisedb, notion, weekly_plan as weekly_plan_service


def _day(value: str | None) -> str | None:
    return notion.coerce_date(value) if value else None


def register_tools(mcp: FastMCP) -> None:
    def store() -> notion.NotionStore:
        return notion.NotionStore()

    @mcp.tool
    async def list_lifting_workouts(
        athlete: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List lift rows from the Notion Workout Lifts database (source of truth)."""
        return await store().list_lifts(athlete=athlete, date_from=_day(date_from), date_to=_day(date_to))

    @mcp.tool
    async def get_lifting_workout(item_id: str) -> dict[str, Any]:
        """Get one Notion lift row by page id."""
        return await store().get_lift(item_id)

    @mcp.tool
    async def create_lifting_workout(
        lift: str,
        goal_weight: str,
        reps: int,
        date_todo: str,
        athlete: str | None = None,
        actual_weight: str | None = None,
        completed: bool = False,
        week_start: str | None = None,
    ) -> dict[str, Any]:
        """Create a lift in Notion. Leave actual_weight empty until the set is done."""
        day = _day(date_todo)
        start = _day(week_start) or (
            weekly_plan_service.monday_of(date.fromisoformat(day)).isoformat() if day else None
        )
        return await store().create_lift(
            {
                "lift": lift,
                "goal_weight": goal_weight,
                "reps": reps,
                "date": day,
                "athlete": athlete,
                "actual_weight": actual_weight,
                "completed": completed,
                "week_start": start,
            }
        )

    @mcp.tool
    async def update_lifting_workout(
        item_id: str,
        lift: str | None = None,
        goal_weight: str | None = None,
        reps: int | None = None,
        date_todo: str | None = None,
        actual_weight: str | None = None,
        completed: bool | None = None,
        athlete: str | None = None,
    ) -> dict[str, Any]:
        """Update a Notion lift row. Use this after logging Actual weight, or the user can edit Notion directly."""
        data: dict[str, Any] = {}
        if lift is not None:
            data["lift"] = lift
        if goal_weight is not None:
            data["goal_weight"] = goal_weight
        if reps is not None:
            data["reps"] = reps
        if date_todo is not None:
            data["date"] = _day(date_todo)
        if actual_weight is not None:
            data["actual_weight"] = actual_weight
        if completed is not None:
            data["completed"] = completed
        if athlete is not None:
            data["athlete"] = athlete
        return await store().update_lift(item_id, data)

    @mcp.tool
    async def delete_lifting_workout(item_id: str) -> str:
        """Archive a Notion lift row."""
        return await store().delete_lift(item_id)

    async def _upsert_log(athlete: str | None, date_todo: str, **fields: Any) -> dict[str, Any]:
        return await store().upsert_log({"athlete": athlete, "date": _day(date_todo), **fields})

    @mcp.tool
    async def list_cardio(
        athlete: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List daily Notion logs that include cardio."""
        rows = await store().list_logs(athlete=athlete, date_from=_day(date_from), date_to=_day(date_to))
        return [row for row in rows if row.get("cardio_kind") or row.get("distance")]

    @mcp.tool
    async def create_cardio(
        distance: str,
        reps: int,
        date_todo: str,
        sprint: bool = False,
        run: bool = False,
        walk: bool = False,
        completed: bool = False,
        athlete: str | None = None,
    ) -> dict[str, Any]:
        """Write cardio onto that day's Notion Daily Log row."""
        return await _upsert_log(
            athlete,
            date_todo,
            distance=distance,
            cardio_reps=reps,
            sprint=sprint,
            run=run,
            walk=walk,
            cardio_completed=completed,
        )

    @mcp.tool
    async def update_cardio(
        item_id: str,
        distance: str | None = None,
        reps: int | None = None,
        sprint: bool | None = None,
        run: bool | None = None,
        walk: bool | None = None,
        completed: bool | None = None,
    ) -> dict[str, Any]:
        """Update cardio fields on a Daily Log row."""
        current = await store().get_log(item_id)
        data = {
            "date": current.get("date"),
            "athlete": current.get("athlete"),
            "distance": distance if distance is not None else current.get("distance"),
            "cardio_reps": reps if reps is not None else current.get("cardio_reps"),
            "sprint": sprint if sprint is not None else current.get("sprint"),
            "run": run if run is not None else current.get("run"),
            "walk": walk if walk is not None else current.get("walk"),
            "cardio_completed": completed if completed is not None else current.get("cardio_completed"),
            "protein_goal": current.get("protein_goal"),
            "protein_actual": current.get("protein_actual"),
            "steps_goal": current.get("steps_goal"),
            "steps_actual": current.get("steps_actual"),
        }
        return await store().upsert_log(data)

    @mcp.tool
    async def delete_cardio(item_id: str) -> str:
        """Clear cardio fields on a Daily Log, or archive the row if it has nothing else."""
        current = await store().get_log(item_id)
        if not current.get("protein_goal") and not current.get("steps_goal"):
            return await store().delete_log(item_id)
        current.update(
            {
                "sprint": False,
                "run": False,
                "walk": False,
                "distance": None,
                "cardio_reps": None,
                "cardio_completed": False,
            }
        )
        return await store().upsert_log(current)

    @mcp.tool
    async def list_protein(
        athlete: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List daily Notion logs that include protein."""
        rows = await store().list_logs(athlete=athlete, date_from=_day(date_from), date_to=_day(date_to))
        return [row for row in rows if row.get("protein_goal") is not None or row.get("protein_actual") is not None]

    @mcp.tool
    async def create_protein(
        grams_goal: int,
        grams_actual: int,
        date_todo: str,
        athlete: str | None = None,
    ) -> dict[str, Any]:
        """Write protein onto that day's Notion Daily Log row."""
        return await _upsert_log(athlete, date_todo, protein_goal=grams_goal, protein_actual=grams_actual)

    @mcp.tool
    async def update_protein(
        item_id: str,
        grams_goal: int | None = None,
        grams_actual: int | None = None,
    ) -> dict[str, Any]:
        current = await store().get_log(item_id)
        if grams_goal is not None:
            current["protein_goal"] = grams_goal
        if grams_actual is not None:
            current["protein_actual"] = grams_actual
        return await store().upsert_log(current)

    @mcp.tool
    async def delete_protein(item_id: str) -> str:
        current = await store().get_log(item_id)
        current["protein_goal"] = None
        current["protein_actual"] = None
        if not current.get("cardio_kind") and current.get("steps_goal") is None:
            return await store().delete_log(item_id)
        return await store().upsert_log(current)

    @mcp.tool
    async def list_steps(
        athlete: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List daily Notion logs that include steps."""
        rows = await store().list_logs(athlete=athlete, date_from=_day(date_from), date_to=_day(date_to))
        return [row for row in rows if row.get("steps_goal") is not None or row.get("steps_actual") is not None]

    @mcp.tool
    async def create_steps(
        steps_goal: int,
        steps_actual: int,
        date_todo: str,
        athlete: str | None = None,
    ) -> dict[str, Any]:
        """Write steps onto that day's Notion Daily Log row."""
        return await _upsert_log(athlete, date_todo, steps_goal=steps_goal, steps_actual=steps_actual)

    @mcp.tool
    async def update_steps(
        item_id: str,
        steps_goal: int | None = None,
        steps_actual: int | None = None,
    ) -> dict[str, Any]:
        current = await store().get_log(item_id)
        if steps_goal is not None:
            current["steps_goal"] = steps_goal
        if steps_actual is not None:
            current["steps_actual"] = steps_actual
        return await store().upsert_log(current)

    @mcp.tool
    async def delete_steps(item_id: str) -> str:
        current = await store().get_log(item_id)
        current["steps_goal"] = None
        current["steps_actual"] = None
        if not current.get("cardio_kind") and current.get("protein_goal") is None:
            return await store().delete_log(item_id)
        return await store().upsert_log(current)

    @mcp.tool
    async def get_recent_lift_performance(athlete: str | None = None) -> dict[str, Any]:
        """Latest lift rows from Notion, one per lift name. Use Actual weight for next week's goals."""
        return {"lifts": await store().recent_performance(athlete)}

    @mcp.tool
    async def search_exercise_videos(
        name: str | None = None,
        body_parts: str | None = None,
        equipments: str | None = None,
        target_muscles: str | None = None,
        exercise_type: str | None = None,
        keywords: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search ExerciseDB for demonstration videos or GIFs."""
        exercises, total = await exercisedb.search_exercises(
            name=name,
            body_parts=body_parts,
            equipments=equipments,
            target_muscles=target_muscles,
            exercise_type=exercise_type,
            keywords=keywords,
            limit=limit,
        )
        return {
            "source": exercisedb.exercisedb_source(),
            "total": total,
            "exercises": [item.model_dump() for item in exercises],
        }

    @mcp.tool
    async def get_exercise_video(exercise_id: str) -> dict[str, Any]:
        """Get one ExerciseDB exercise by id."""
        return (await exercisedb.get_exercise(exercise_id)).model_dump()

    @mcp.tool
    async def publish_weekly_workout_to_notion(
        athlete: str | None = None,
        week_start: str | None = None,
        week_end: str | None = None,
        title: str | None = None,
        focus: str | None = None,
        notes: str | None = None,
        include_videos: bool = True,
        dry_run: bool = False,
        plan_json: str | None = None,
    ) -> dict[str, Any]:
        """Publish a readable weekly page from Notion lift/log rows (or plan_json).

        Lift rows already in Workout Lifts stay the source of truth. This only builds
        the week page you open and work from.
        """
        if plan_json:
            plan = WeeklyPlan.model_validate(json.loads(plan_json))
            if include_videos:
                plan = await weekly_plan_service.attach_videos(plan)
        else:
            who = notion._require_athlete(athlete)
            start = weekly_plan_service.parse_week_start(week_start)
            end = weekly_plan_service.week_end_for(start, week_end)
            plan = await weekly_plan_service.assemble_weekly_plan(
                athlete=who,
                week_start=start,
                week_end=end,
                focus=focus,
                notes=notes,
                title=title,
                include_videos=include_videos,
                store=store(),
            )
        if title:
            plan.title = title
        if focus:
            plan.focus = focus
        if notes:
            plan.notes = notes
        return await notion.publish_weekly_plan(plan, dry_run=dry_run)
