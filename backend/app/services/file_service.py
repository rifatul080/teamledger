"""File library service."""
from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..core.errors import not_found, validation
from ..core.ids import new_id
from ..models.file import FileEntry, FileVersion
from ..models.team import Team
from ..models.user import User
from ..storage.base import (
    safe_basename,
    safe_inline_preview,
    safe_member_name,
    sniff_content_type,
)


class StorageLike:
    """Minimal interface the service relies on (duck-typed)."""

    def put(self, *, team_id: str, content: bytes, original_name: str):
        ...

    def head(self, path: str):
        ...

    def stream(self, path: str):
        ...

    def delete(self, path: str) -> None:
        ...


def add_file(
    db: Session,
    *,
    team: Team,
    uploader: User,
    storage: StorageLike,
    content: bytes,
    original_name: str,
    folder: str = "/",
) -> tuple[FileEntry, FileVersion]:
    if not content:
        raise validation("Empty file.", code="file.empty")
    safe = safe_basename(original_name)
    # Sniff content type; never trust client.
    detected = sniff_content_type(content)
    # Persist bytes
    obj = storage.put(team_id=team.id, content=content, original_name=safe)
    now = datetime.now(tz=UTC)
    # Find existing file row with same (team, folder, name) → version up.
    existing = (
        db.query(FileEntry)
        .filter(FileEntry.team_id == team.id, FileEntry.folder == folder, FileEntry.name == safe)
        .one_or_none()
    )
    if existing is None:
        existing = FileEntry(
            id=new_id(),
            team_id=team.id,
            folder=folder,
            name=safe,
            current_version_id=None,
            uploader_user_id=uploader.id,
            created_at=now,
        )
        db.add(existing)
        db.flush()
        next_version = 1
    else:
        last_version = (
            db.query(FileVersion.version_no)
            .filter(FileVersion.file_id == existing.id)
            .order_by(FileVersion.version_no.desc())
            .first()
        )
        next_version = (last_version[0] if last_version else 0) + 1
    version = FileVersion(
        id=new_id(),
        file_id=existing.id,
        version_no=next_version,
        storage_path=obj.path,
        original_name=safe,
        content_type=detected,
        size_bytes=len(content),
        sha256=obj.sha256,
        uploader_user_id=uploader.id,
        uploaded_at=now,
    )
    db.add(version)
    db.flush()
    existing.current_version_id = version.id
    return existing, version


def list_files(db: Session, *, team_id: str, folder: str | None = None) -> list[tuple[FileEntry, FileVersion | None]]:
    q = db.query(FileEntry).filter(FileEntry.team_id == team_id)
    if folder is not None:
        q = q.filter(FileEntry.folder == folder)
    rows = q.order_by(FileEntry.name.asc()).all()
    out: list[tuple[FileEntry, FileVersion | None]] = []
    for fe in rows:
        v = db.get(FileVersion, fe.current_version_id) if fe.current_version_id else None
        out.append((fe, v))
    return out


def get_file(db: Session, *, team_id: str, file_id: str) -> FileEntry:
    fe = db.get(FileEntry, file_id)
    if fe is None or fe.team_id != team_id:
        raise not_found(code="file.not_found")
    return fe


def list_versions(db: Session, *, file_id: str) -> list[FileVersion]:
    return (
        db.query(FileVersion)
        .filter(FileVersion.file_id == file_id)
        .order_by(FileVersion.version_no.desc())
        .all()
    )


def can_preview_inline(content_type: str) -> bool:
    return safe_inline_preview(content_type)


def archive_entry_safe(name: str) -> bool:
    return safe_member_name(name)


def inspect_zip_safety(content: bytes) -> tuple[bool, list[str]]:
    """Return ``(safe, bad_members)``.

    Reject archives with members that try to escape the directory, are absolute,
    or contain null bytes. We never unpack; this check is for display-time
    safety only.
    """
    bad: list[str] = []
    try:
        bio = io.BytesIO(content)
        with zipfile.ZipFile(bio) as zf:
            for info in zf.infolist():
                if not safe_member_name(info.filename):
                    bad.append(info.filename)
    except zipfile.BadZipFile:
        bad.append("__bad_zip__")
    return not bad, bad
