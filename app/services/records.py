import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def resolve_user(
    session: AsyncSession,
    *,
    email: str | None = None,
    user_id: uuid.UUID | str | None = None,
) -> User:
    if user_id is not None:
        parsed = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        user = await session.get(User, parsed)
        if user is None:
            raise ValueError(f"No user with id {parsed}")
        if email and user.email.lower() != email.lower():
            raise ValueError("email and user_id do not match the same user")
        return user
    if email:
        result = await session.execute(select(User).where(User.email.ilike(email)))
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"No user with email {email}")
        return user
    raise ValueError("Provide email or user_id")


async def list_for_user(
    session: AsyncSession,
    model: type,
    user_id: uuid.UUID,
    *,
    date_field: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Any]:
    stmt: Select = select(model).where(model.user_id == user_id)
    if date_field and date_from is not None:
        stmt = stmt.where(getattr(model, date_field) >= date_from)
    if date_field and date_to is not None:
        stmt = stmt.where(getattr(model, date_field) <= date_to)
    if date_field:
        stmt = stmt.order_by(getattr(model, date_field).desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_for_user(session: AsyncSession, model: type, user_id: uuid.UUID, item_id: uuid.UUID):
    item = await session.get(model, item_id)
    if item is None or item.user_id != user_id:
        return None
    return item


async def create_for_user(session: AsyncSession, model: type, user_id: uuid.UUID, data: dict[str, Any]):
    item = model(user_id=user_id, **data)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_for_user(
    session: AsyncSession,
    model: type,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    data: dict[str, Any],
):
    item = await get_for_user(session, model, user_id, item_id)
    if item is None:
        return None
    for key, value in data.items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


async def delete_for_user(
    session: AsyncSession,
    model: type,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
) -> bool:
    item = await get_for_user(session, model, user_id, item_id)
    if item is None:
        return False
    await session.delete(item)
    await session.commit()
    return True


def to_dict(item: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, uuid.UUID):
            data[column.name] = str(value)
        elif isinstance(value, datetime):
            data[column.name] = value.isoformat()
        else:
            data[column.name] = value
    return data
