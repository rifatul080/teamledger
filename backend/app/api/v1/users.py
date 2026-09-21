"""User /me endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import current_user, get_db
from ...models.user import User
from ...schemas.auth import UserPublic
from ...schemas.users import ProfileUpdate

router = APIRouter(prefix="/me", tags=["users"])


@router.get("", response_model=UserPublic)
def me(user: User = Depends(current_user)) -> UserPublic:
    return UserPublic.model_validate(user)


@router.patch("", response_model=UserPublic)
def update_me(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> UserPublic:
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.timezone is not None:
        user.timezone = payload.timezone
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)
