from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastmcp import FastMCP

from app import db as db_module
from app.models.body_stats import BodyStats
from app.models.cardio import Cardio
from app.models.gym_location import GymLocation
from app.models.lifting_workout import LiftingWorkout
from app.models.performance_goal import PerformanceGoal
from app.models.physic_photo import PhysicPhoto
from app.models.protein import Protein
from app.models.steps import Steps
from app.services import records


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool
    async def resolve_user(email: str | None = None, user_id: str | None = None) -> dict[str, Any]:
        """Look up a workout-app user by email or user_id. Provide one or both."""
        async with db_module.SessionLocal() as session:
            user = await records.resolve_user(session, email=email, user_id=user_id)
            return {"id": str(user.id), "email": user.email, "name": user.name}

    async def _list(model, date_field, email, user_id, date_from, date_to):
        async with db_module.SessionLocal() as session:
            user = await records.resolve_user(session, email=email, user_id=user_id)
            items = await records.list_for_user(
                session,
                model,
                user.id,
                date_field=date_field,
                date_from=_parse_dt(date_from) if date_from else None,
                date_to=_parse_dt(date_to) if date_to else None,
            )
            return [records.to_dict(item) for item in items]

    async def _get(model, item_id, email, user_id):
        async with db_module.SessionLocal() as session:
            user = await records.resolve_user(session, email=email, user_id=user_id)
            item = await records.get_for_user(session, model, user.id, UUID(item_id))
            if item is None:
                raise ValueError("Not found")
            return records.to_dict(item)

    async def _create(model, data, email, user_id):
        async with db_module.SessionLocal() as session:
            user = await records.resolve_user(session, email=email, user_id=user_id)
            item = await records.create_for_user(session, model, user.id, data)
            return records.to_dict(item)

    async def _update(model, item_id, data, email, user_id):
        async with db_module.SessionLocal() as session:
            user = await records.resolve_user(session, email=email, user_id=user_id)
            item = await records.update_for_user(session, model, user.id, UUID(item_id), data)
            if item is None:
                raise ValueError("Not found")
            return records.to_dict(item)

    async def _delete(model, item_id, email, user_id) -> str:
        async with db_module.SessionLocal() as session:
            user = await records.resolve_user(session, email=email, user_id=user_id)
            deleted = await records.delete_for_user(session, model, user.id, UUID(item_id))
            if not deleted:
                raise ValueError("Not found")
            return "deleted"

    @mcp.tool
    async def list_lifting_workouts(
        email: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List lifting workouts for a user. Optional ISO date_from / date_to filters."""
        return await _list(LiftingWorkout, "date_todo", email, user_id, date_from, date_to)

    @mcp.tool
    async def get_lifting_workout(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one lifting workout by id for a user."""
        return await _get(LiftingWorkout, item_id, email, user_id)

    @mcp.tool
    async def create_lifting_workout(
        lift: str,
        goal_weight: str,
        reps: int,
        actual_weight: str,
        date_todo: str,
        completed: bool = False,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a lifting workout for a user. date_todo is ISO-8601."""
        return await _create(
            LiftingWorkout,
            {
                "lift": lift,
                "goal_weight": goal_weight,
                "reps": reps,
                "actual_weight": actual_weight,
                "completed": completed,
                "date_todo": _parse_dt(date_todo),
            },
            email,
            user_id,
        )

    @mcp.tool
    async def update_lifting_workout(
        item_id: str,
        lift: str | None = None,
        goal_weight: str | None = None,
        reps: int | None = None,
        actual_weight: str | None = None,
        completed: bool | None = None,
        date_todo: str | None = None,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a lifting workout. Only provided fields are changed."""
        data: dict[str, Any] = {}
        if lift is not None:
            data["lift"] = lift
        if goal_weight is not None:
            data["goal_weight"] = goal_weight
        if reps is not None:
            data["reps"] = reps
        if actual_weight is not None:
            data["actual_weight"] = actual_weight
        if completed is not None:
            data["completed"] = completed
        if date_todo is not None:
            data["date_todo"] = _parse_dt(date_todo)
        return await _update(LiftingWorkout, item_id, data, email, user_id)

    @mcp.tool
    async def delete_lifting_workout(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Delete a lifting workout."""
        return await _delete(LiftingWorkout, item_id, email, user_id)

    @mcp.tool
    async def list_cardio(
        email: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List cardio sessions for a user."""
        return await _list(Cardio, "date_todo", email, user_id, date_from, date_to)

    @mcp.tool
    async def get_cardio(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one cardio session by id."""
        return await _get(Cardio, item_id, email, user_id)

    @mcp.tool
    async def create_cardio(
        distance: str,
        reps: int,
        date_todo: str,
        sprint: bool = False,
        run: bool = False,
        walk: bool = False,
        completed: bool = False,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a cardio session for a user."""
        return await _create(
            Cardio,
            {
                "sprint": sprint,
                "run": run,
                "walk": walk,
                "distance": distance,
                "reps": reps,
                "completed": completed,
                "date_todo": _parse_dt(date_todo),
            },
            email,
            user_id,
        )

    @mcp.tool
    async def update_cardio(
        item_id: str,
        distance: str | None = None,
        reps: int | None = None,
        date_todo: str | None = None,
        sprint: bool | None = None,
        run: bool | None = None,
        walk: bool | None = None,
        completed: bool | None = None,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a cardio session."""
        data: dict[str, Any] = {}
        if distance is not None:
            data["distance"] = distance
        if reps is not None:
            data["reps"] = reps
        if date_todo is not None:
            data["date_todo"] = _parse_dt(date_todo)
        if sprint is not None:
            data["sprint"] = sprint
        if run is not None:
            data["run"] = run
        if walk is not None:
            data["walk"] = walk
        if completed is not None:
            data["completed"] = completed
        return await _update(Cardio, item_id, data, email, user_id)

    @mcp.tool
    async def delete_cardio(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Delete a cardio session."""
        return await _delete(Cardio, item_id, email, user_id)

    @mcp.tool
    async def list_protein(
        email: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List protein logs for a user."""
        return await _list(Protein, "date_todo", email, user_id, date_from, date_to)

    @mcp.tool
    async def get_protein(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one protein log by id."""
        return await _get(Protein, item_id, email, user_id)

    @mcp.tool
    async def create_protein(
        grams_goal: int,
        grams_actual: int,
        date_todo: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a protein log for a user."""
        return await _create(
            Protein,
            {
                "grams_goal": grams_goal,
                "grams_actual": grams_actual,
                "date_todo": _parse_dt(date_todo),
            },
            email,
            user_id,
        )

    @mcp.tool
    async def update_protein(
        item_id: str,
        grams_goal: int | None = None,
        grams_actual: int | None = None,
        date_todo: str | None = None,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a protein log."""
        data: dict[str, Any] = {}
        if grams_goal is not None:
            data["grams_goal"] = grams_goal
        if grams_actual is not None:
            data["grams_actual"] = grams_actual
        if date_todo is not None:
            data["date_todo"] = _parse_dt(date_todo)
        return await _update(Protein, item_id, data, email, user_id)

    @mcp.tool
    async def delete_protein(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Delete a protein log."""
        return await _delete(Protein, item_id, email, user_id)

    @mcp.tool
    async def list_steps(
        email: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List step logs for a user."""
        return await _list(Steps, "date_todo", email, user_id, date_from, date_to)

    @mcp.tool
    async def get_steps(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one step log by id."""
        return await _get(Steps, item_id, email, user_id)

    @mcp.tool
    async def create_steps(
        steps_goal: int,
        steps_actual: int,
        date_todo: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a step log for a user."""
        return await _create(
            Steps,
            {
                "steps_goal": steps_goal,
                "steps_actual": steps_actual,
                "date_todo": _parse_dt(date_todo),
            },
            email,
            user_id,
        )

    @mcp.tool
    async def update_steps(
        item_id: str,
        steps_goal: int | None = None,
        steps_actual: int | None = None,
        date_todo: str | None = None,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a step log."""
        data: dict[str, Any] = {}
        if steps_goal is not None:
            data["steps_goal"] = steps_goal
        if steps_actual is not None:
            data["steps_actual"] = steps_actual
        if date_todo is not None:
            data["date_todo"] = _parse_dt(date_todo)
        return await _update(Steps, item_id, data, email, user_id)

    @mcp.tool
    async def delete_steps(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Delete a step log."""
        return await _delete(Steps, item_id, email, user_id)

    @mcp.tool
    async def list_gym_locations(
        email: str | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List gym locations for a user (read-only for the agent)."""
        return await _list(GymLocation, None, email, user_id, None, None)

    @mcp.tool
    async def get_gym_location(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one gym location by id (read-only for the agent)."""
        return await _get(GymLocation, item_id, email, user_id)

    @mcp.tool
    async def list_performance_goals(
        email: str | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List performance goals for a user (read-only for the agent)."""
        return await _list(PerformanceGoal, None, email, user_id, None, None)

    @mcp.tool
    async def get_performance_goal(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one performance goal by id (read-only for the agent)."""
        return await _get(PerformanceGoal, item_id, email, user_id)

    @mcp.tool
    async def list_physic_photos(
        email: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List physique photos metadata for a user (read-only for the agent)."""
        return await _list(PhysicPhoto, "date", email, user_id, date_from, date_to)

    @mcp.tool
    async def get_physic_photo(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one physique photo record by id (read-only for the agent)."""
        return await _get(PhysicPhoto, item_id, email, user_id)

    @mcp.tool
    async def list_body_stats(
        email: str | None = None,
        user_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """List height, weight, and main-lift stats for a user (read-only for the agent). Null lifts mean I don't know."""
        return await _list(BodyStats, "date", email, user_id, date_from, date_to)

    @mcp.tool
    async def get_body_stats(
        item_id: str,
        email: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get one body-stats snapshot by id (read-only for the agent)."""
        return await _get(BodyStats, item_id, email, user_id)
