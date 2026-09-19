from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from app.graph.planner import run_week
from app.schemas.weekly_plan import WeeklyPlan
from app.services import exercisedb, weekly_plan as weekly_plan_service
from app.services.workspace import setup_workspace


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool
    async def pull_planning_context(
        week_start: str | None = None,
        week_end: str | None = None,
    ) -> dict[str, Any]:
        """Pull Notion data the LangGraph needs: recent lifts, goals, locations, body stats, recent logs."""
        start = weekly_plan_service.parse_week_start(week_start)
        end = weekly_plan_service.week_end_for(start, week_end)
        context = await weekly_plan_service.pull_context(week_start=start, week_end=end)
        return context.model_dump(mode="json")

    @mcp.tool
    async def push_weekly_plan(
        plan_json: str,
        include_videos: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Push the graph's finished WeeklyPlan to Notion: lift rows, daily logs, week page + demos."""
        plan = WeeklyPlan.model_validate(json.loads(plan_json))
        return await weekly_plan_service.push_plan(
            plan,
            dry_run=dry_run,
            include_videos=include_videos,
        )

    @mcp.tool
    async def run_weekly_planner(
        week_start: str | None = None,
        week_end: str | None = None,
        include_videos: bool = True,
        dry_run: bool = False,
        push: bool = True,
    ) -> dict[str, Any]:
        """Pull Notion, run the LangGraph planner (gpt-5.6-luna), optionally push the week."""
        return await run_week(
            week_start=week_start,
            week_end=week_end,
            dry_run=dry_run,
            include_videos=include_videos,
            push=push,
        )

    @mcp.tool
    async def setup_notion_workspace(
        parent_page: str,
        in_place: bool = False,
        seed: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Create the Workout Agent Notion page and six databases from this repo's schema."""
        return await setup_workspace(
            parent_page,
            dry_run=dry_run,
            in_place=in_place,
            seed=seed,
        )

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
        """Optional: search ExerciseDB while the graph is planning."""
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
        """Optional: get one ExerciseDB exercise by id."""
        return (await exercisedb.get_exercise(exercise_id)).model_dump()
