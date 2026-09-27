"""Personal notes endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import current_user, get_db
from ...core.errors import not_found
from ...core.ids import new_id
from ...models.note import Note
from ...models.user import User
from ...schemas.notes import NoteCreate, NoteRead, NoteUpdate

router = APIRouter(prefix="/me/notes", tags=["notes"])


@router.get("", response_model=list[NoteRead])
def list_notes(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[NoteRead]:
    notes = (
        db.query(Note)
        .filter(Note.user_id == user.id)
        .order_by(Note.pinned.desc(), Note.created_at.desc())
        .all()
    )
    return [NoteRead.model_validate(n) for n in notes]


@router.post("", response_model=NoteRead, status_code=201)
def create_note(
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> NoteRead:
    note = Note(
        id=new_id(),
        user_id=user.id,
        title=payload.title,
        content=payload.content,
        pinned=payload.pinned,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteRead.model_validate(note)


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(
    note_id: str,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> NoteRead:
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == user.id).one_or_none()
    if note is None:
        raise not_found(code="note.not_found")
    if payload.title is not None:
        note.title = payload.title
    if payload.content is not None:
        note.content = payload.content
    if payload.pinned is not None:
        note.pinned = payload.pinned
    note.updated_at = datetime.now(tz=UTC)
    db.commit()
    db.refresh(note)
    return NoteRead.model_validate(note)


@router.delete("/{note_id}", status_code=204)
def delete_note(
    note_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    note = db.query(Note).filter(Note.id == note_id, Note.user_id == user.id).one_or_none()
    if note is not None:
        db.delete(note)
        db.commit()
