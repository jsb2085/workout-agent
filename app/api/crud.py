import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.services import records


def crud_router(
    model: type,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    *,
    prefix: str,
    tags: list[str],
    date_field: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=tags)

    @router.get("/", response_model=list[read_schema])
    async def list_items(
        session: SessionDep,
        user: CurrentUser,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        return await records.list_for_user(
            session,
            model,
            user.id,
            date_field=date_field,
            date_from=date_from,
            date_to=date_to,
        )

    @router.get("/{item_id}", response_model=read_schema)
    async def get_item(item_id: uuid.UUID, session: SessionDep, user: CurrentUser):
        item = await records.get_for_user(session, model, user.id, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return item

    @router.post("/", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    async def create_item(body: create_schema, session: SessionDep, user: CurrentUser):  # type: ignore[valid-type]
        return await records.create_for_user(session, model, user.id, body.model_dump())

    @router.patch("/{item_id}", response_model=read_schema)
    async def update_item(
        item_id: uuid.UUID,
        body: update_schema,  # type: ignore[valid-type]
        session: SessionDep,
        user: CurrentUser,
    ):
        item = await records.update_for_user(
            session,
            model,
            user.id,
            item_id,
            body.model_dump(exclude_unset=True),
        )
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return item

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_item(item_id: uuid.UUID, session: SessionDep, user: CurrentUser):
        deleted = await records.delete_for_user(session, model, user.id, item_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return router
