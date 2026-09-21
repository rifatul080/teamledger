"""File library endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership
from ...core.config import get_settings
from ...core.errors import not_found, validation
from ...models.file import FileVersion
from ...models.team import Team
from ...models.user import User
from ...schemas.files import FileRead, FileVersionRead
from ...services import file_service

router = APIRouter(tags=["files"])


def _storage():
    from ...core.config import get_settings
    from ...storage.local import make_storage

    s = get_settings()
    return make_storage(s.storage_backend, s.storage_local_root)


@router.post("/teams/{team_id}/files", response_model=FileRead, status_code=201)
async def upload(
    team_id: str,
    file: UploadFile = File(...),
    folder: str = Query(default="/"),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> FileRead:
    require_membership(team_id, db, user.id)
    settings = get_settings()
    content = await file.read()
    if len(content) > settings.file_max_bytes:
        raise validation(
            f"File too large. Max {settings.file_max_bytes} bytes.",
            code="file.too_large",
        )
    fe, ver = file_service.add_file(
        db, team=db.get(Team, team_id), uploader=user, storage=_storage(),
        content=content, original_name=file.filename or "file", folder=folder,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=team_id,
        action="file.upload",
        subject_kind="file",
        subject_id=fe.id,
        payload={"version_no": ver.version_no, "size": ver.size_bytes},
    )
    db.commit()
    return FileRead(
        id=fe.id,
        team_id=fe.team_id,
        folder=fe.folder,
        name=fe.name,
        current_version_no=ver.version_no,
        size_bytes=ver.size_bytes,
        content_type=ver.content_type,
        sha256=ver.sha256,
        uploader_user_id=ver.uploader_user_id,
        updated_at=ver.uploaded_at,
    )


@router.get("/teams/{team_id}/files", response_model=list[FileRead])
def list_files(
    team_id: str,
    folder: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[FileRead]:
    require_membership(team_id, db, user.id)
    rows = file_service.list_files(db, team_id=team_id, folder=folder)
    out: list[FileRead] = []
    for fe, ver in rows:
        if ver is None:
            continue
        out.append(
            FileRead(
                id=fe.id,
                team_id=fe.team_id,
                folder=fe.folder,
                name=fe.name,
                current_version_no=ver.version_no,
                size_bytes=ver.size_bytes,
                content_type=ver.content_type,
                sha256=ver.sha256,
                uploader_user_id=ver.uploader_user_id,
                updated_at=ver.uploaded_at,
            )
        )
    return out


@router.get("/teams/{team_id}/files/{file_id}/versions", response_model=list[FileVersionRead])
def list_versions(
    team_id: str,
    file_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[FileVersionRead]:
    require_membership(team_id, db, user.id)
    fe = file_service.get_file(db, team_id=team_id, file_id=file_id)
    rows = file_service.list_versions(db, file_id=fe.id)
    return [
        FileVersionRead(
            version_no=r.version_no,
            size_bytes=r.size_bytes,
            content_type=r.content_type,
            sha256=r.sha256,
            uploader_user_id=r.uploader_user_id,
            uploaded_at=r.uploaded_at,
            original_name=r.original_name,
        )
        for r in rows
    ]


@router.get("/teams/{team_id}/files/{file_id}/download")
def download(
    team_id: str,
    file_id: str,
    version: int | None = Query(default=None),
    inline: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    require_membership(team_id, db, user.id)
    fe = file_service.get_file(db, team_id=team_id, file_id=file_id)
    if version is not None:
        ver = (
            db.query(FileVersion)
            .filter(FileVersion.file_id == fe.id, FileVersion.version_no == version)
            .one_or_none()
        )
        if ver is None:
            raise not_found(code="file.version_not_found")
    else:
        ver = db.get(FileVersion, fe.current_version_id)
        if ver is None:
            raise not_found()
    storage = _storage()
    if not storage.exists(ver.storage_path):
        raise not_found(code="file.blob_missing")

    disposition = "inline" if (inline and file_service.can_preview_inline(ver.content_type)) else "attachment"
    safe_name = ver.original_name.replace('"', "_")
    headers = {
        "Content-Disposition": f'{disposition}; filename="{safe_name}"',
        "X-Content-Type-Options": "nosniff",
        "Content-Length": str(ver.size_bytes),
        "Cache-Control": "private, no-store",
    }
    if disposition == "attachment" or not file_service.can_preview_inline(ver.content_type):
        headers["Content-Type"] = "application/octet-stream"
    else:
        headers["Content-Type"] = ver.content_type

    def _gen():
        yield from storage.stream(ver.storage_path)

    return StreamingResponse(_gen(), headers=headers, media_type=headers["Content-Type"])


@router.post("/teams/{team_id}/files/check-archive", response_model=dict)
async def check_archive(
    team_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Return safety info for an uploaded archive (zip)."""
    require_membership(team_id, db, user.id)
    content = await file.read()
    safe, bad = file_service.inspect_zip_safety(content)
    return {"safe": safe, "bad_members": bad}
