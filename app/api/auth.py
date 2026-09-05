from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models.user import User
from app.schemas.auth import GoogleLoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services import google_auth
from app.services.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google", response_model=TokenResponse)
async def google_login(body: GoogleLoginRequest, session: SessionDep) -> TokenResponse:
    try:
        info = google_auth.verify_google_id_token(body.id_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    result = await session.execute(select(User).where(User.google_sub == info["sub"]))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=info["email"],
            google_sub=info["sub"],
            name=info.get("name"),
        )
        session.add(user)
    else:
        user.email = info["email"]
        user.name = info.get("name", user.name)
    await session.commit()
    await session.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id), user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> User:
    return user
