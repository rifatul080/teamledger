"""User + avatar endpoints (v2)."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session

from ...api.deps import current_user, get_db
from ...api.deps import audit as audit_log
from ...core.config import get_settings
from ...core.errors import AppError
from ...models.user import User
from ...schemas.auth import ProfileUpdate, UserPublic
from ...services import profile_service

router = APIRouter()


# ----- /me -----
@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(current_user)) -> UserPublic:
    return profile_service.build_user_public(user)


@router.patch("/me", response_model=UserPublic)
def update_me(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> UserPublic:
    profile_service.update_profile(
        user,
        display_name=payload.display_name,
        timezone=payload.timezone,
        theme=payload.theme,
        institution=payload.institution,
    )
    audit_log(
        db,
        actor_user_id=user.id,
        action="profile.update",
        subject_kind="user",
        subject_id=user.id,
        payload={
            "display_name": payload.display_name is not None,
            "theme": payload.theme is not None,
            "institution": payload.institution is not None,
            "timezone": payload.timezone is not None,
        },
        when=user.created_at,
    )
    db.commit()
    db.refresh(user)
    return profile_service.build_user_public(user)


# ----- /me/avatar (upload) -----
@router.post("/me/avatar", response_model=dict)
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    settings = get_settings()
    raw = await file.read()
    small_rel, large_rel = profile_service.validate_and_avatar_from_upload(
        user, raw=raw, max_bytes=settings.avatar_max_bytes
    )
    user.avatar_small = small_rel
    user.avatar_large = large_rel
    audit_log(
        db,
        actor_user_id=user.id,
        action="profile.avatar_upload",
        subject_kind="user",
        subject_id=user.id,
        payload={"small": small_rel, "large": large_rel, "size": len(raw)},
        when=user.created_at,
    )
    db.commit()
    return {
        "avatar_url": profile_service.avatar_url_for_user(user, size="small"),
        "avatar_url_small": profile_service.avatar_url_for_user(user, size="small"),
        "avatar_url_large": profile_service.avatar_url_for_user(user, size="large"),
    }


# ----- /users/{user_id}/avatar (download) -----
@router.get("/users/{user_id}/avatar")
def get_avatar(
    user_id: str,
    size: str = Query("small", pattern=r"^(small|large)$"),
    db: Session = Depends(get_db),
) -> Response:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(status_code=404, code="user.not_found", message="User not found.")
    result = profile_service.read_avatar_bytes(user, size=size)
    if result is None:
        raise HTTPException(status_code=404)
    data, content_type = result
    headers = {
        "Cache-Control": "public, max-age=300",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=data, media_type=content_type, headers=headers)


# ----- /users/directory — listing of users you can mention/assign -----
@router.get("/users/directory", response_model=list[dict])
def directory(
    q: str | None = Query(default=None, description="Optional fuzzy filter on display_name or email"),
    db: Session = Depends(get_db),
    current: User = Depends(current_user),
) -> list[dict]:
    """Returns a compact directory of users for mentions and assignee pickers.

    A user appears here if they share at least one team with the caller, OR
    if the caller is searching for a specific email to invite. Removed
    members stay visible with `former: true` so historical mentions resolve.
    """
    from ...models.membership import Membership

    # Teams the caller is currently in.
    caller_team_ids = [
        m.team_id for m in db.query(Membership).filter(Membership.user_id == current.id).all()
    ]
    qset = db.query(User).distinct()
    if q:
        like = f"%{q.lower()}%"
        from sqlalchemy import func, or_
        qset = qset.filter(or_(func.lower(User.display_name).like(like), func.lower(User.email).like(like)))
    rows = qset.limit(200).all()
    out = []
    caller_team_set = set(caller_team_ids)
    for u in rows:
        # Show if caller shares a team OR if filter is exact-email.
        shared = any(
            (m.user_id == u.id)
            for m in db.query(Membership).filter(Membership.user_id == u.id, Membership.team_id.in_(caller_team_set)).all()
        ) if caller_team_set else False
        if not shared and (not q or q.lower() not in (u.email.lower(), u.display_name.lower())):
            continue
        out.append(
            {
                "id": u.id,
                "display_name": u.display_name,
                "email": u.email,
                "avatar_url": profile_service.avatar_url_for_user(u, size="small"),
            }
        )
    return out[:50]


# ----- /users/{user_id} — public-ish profile (members of shared teams) -----
@router.get("/users/{user_id}", response_model=UserPublic)
def user_public(
    user_id: str,
    db: Session = Depends(get_db),
) -> UserPublic:
    u = db.get(User, user_id)
    if u is None:
        raise AppError(status_code=404, code="user.not_found", message="User not found.")
    return profile_service.build_user_public(u)


# ----- /users/{user_id}/avatar_alt (mtime cache-bust helper) -----
@router.get("/users/{user_id}/initials")
def user_initials(
    user_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Returns display_name so the client can build its initials fallback
    without exposing the email address."""
    u = db.get(User, user_id)
    if u is None:
        return {"display_name": "?", "id": user_id}
    return {"display_name": u.display_name, "id": u.id}
