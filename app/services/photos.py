from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.physic_photo import PhysicPhoto
from app.services import records, storage

PRESIGN_SECONDS = 3600


def photo_with_url(photo: PhysicPhoto) -> dict[str, Any]:
    data = records.to_dict(photo)
    data["url"] = storage.presigned_get_url(photo.object_key, PRESIGN_SECONDS)
    data["expires_in_seconds"] = PRESIGN_SECONDS
    return data


async def _latest(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    is_goal: bool | None = None,
    is_current: bool | None = None,
    exclude_id: uuid.UUID | None = None,
) -> PhysicPhoto | None:
    stmt = select(PhysicPhoto).where(PhysicPhoto.user_id == user_id)
    if is_goal is not None:
        stmt = stmt.where(PhysicPhoto.is_goal == is_goal)
    if is_current is not None:
        stmt = stmt.where(PhysicPhoto.is_current == is_current)
    if exclude_id is not None:
        stmt = stmt.where(PhysicPhoto.id != exclude_id)
    stmt = stmt.order_by(PhysicPhoto.date.desc())
    result = await session.execute(stmt)
    return result.scalars().first()


async def physique_comparison(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    """Latest progress photo vs goal photo, with short-lived download URLs."""
    goal = await _latest(session, user_id, is_goal=True)
    latest = await _latest(session, user_id, is_current=True)
    if latest is None:
        latest = await _latest(
            session,
            user_id,
            is_goal=False,
            exclude_id=goal.id if goal is not None else None,
        )
    if latest is not None and goal is not None and latest.id == goal.id:
        latest = await _latest(session, user_id, exclude_id=goal.id)

    missing: list[str] = []
    if latest is None:
        missing.append("latest")
    if goal is None:
        missing.append("goal")

    return {
        "latest": photo_with_url(latest) if latest is not None else None,
        "goal": photo_with_url(goal) if goal is not None else None,
        "missing": missing,
    }
