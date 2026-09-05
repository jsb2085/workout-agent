import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.models.physic_photo import PhysicPhoto
from app.schemas.physic_photo import PhysicPhotoRead, PhysicPhotoUpdate, PhysicPhotoUrl
from app.services import records, storage

router = APIRouter(prefix="/physic-photos", tags=["physic-photos"])

PRESIGN_SECONDS = 3600


@router.get("/", response_model=list[PhysicPhotoRead])
async def list_photos(
    session: SessionDep,
    user: CurrentUser,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    return await records.list_for_user(
        session,
        PhysicPhoto,
        user.id,
        date_field="date",
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{item_id}", response_model=PhysicPhotoRead)
async def get_photo(item_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    item = await records.get_for_user(session, PhysicPhoto, user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return item


@router.get("/{item_id}/url", response_model=PhysicPhotoUrl)
async def get_photo_url(item_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    item = await records.get_for_user(session, PhysicPhoto, user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    url = storage.presigned_get_url(item.object_key, PRESIGN_SECONDS)
    return PhysicPhotoUrl(url=url, expires_in_seconds=PRESIGN_SECONDS)


@router.post("/", response_model=PhysicPhotoRead, status_code=status.HTTP_201_CREATED)
async def create_photo(
    session: SessionDep,
    user: CurrentUser,
    picture: UploadFile = File(...),
    is_goal: bool = Form(False),
    is_current: bool = Form(False),
    date: datetime = Form(...),
):
    data = await picture.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty image")
    object_key = storage.build_object_key(user.id, picture.filename or "photo.jpg")
    storage.upload_image(object_key, data, picture.content_type or "image/jpeg")
    return await records.create_for_user(
        session,
        PhysicPhoto,
        user.id,
        {
            "object_key": object_key,
            "is_goal": is_goal,
            "is_current": is_current,
            "date": date,
        },
    )


@router.patch("/{item_id}", response_model=PhysicPhotoRead)
async def update_photo(
    item_id: uuid.UUID,
    body: PhysicPhotoUpdate,
    session: SessionDep,
    user: CurrentUser,
):
    item = await records.update_for_user(
        session,
        PhysicPhoto,
        user.id,
        item_id,
        body.model_dump(exclude_unset=True),
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(item_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    item = await records.get_for_user(session, PhysicPhoto, user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        storage.delete_image(item.object_key)
    except Exception:
        pass
    await records.delete_for_user(session, PhysicPhoto, user.id, item_id)
