"""Chat service."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.errors import forbidden
from ..core.ids import new_id
from ..models.message import ChatMessage, MessageRead
from ..models.team import Team
from ..models.user import User


def next_seq(db: Session, team_id: str) -> int:
    """Server-assigned monotonic per-team sequence number.

    Uses the highest existing seq + 1. Within a single process this is safe;
    multi-worker deployments add a Postgres SEQUENCE on the column.
    """
    last = (
        db.query(func.max(ChatMessage.seq))
        .filter(ChatMessage.team_id == team_id)
        .scalar()
    )
    return int(last or 0) + 1


def parse_mentions(body: str, team_member_names: dict[str, str]) -> list[str]:
    """Resolve @display_name patterns to user_ids. Names are matched case-insensitively."""
    import re

    out: list[str] = []
    name_to_uid = {n.lower(): uid for uid, n in team_member_names.items()}
    for match in re.finditer(r"@([A-Za-z0-9_\- ]{1,60})", body):
        key = match.group(1).strip().lower()
        uid = name_to_uid.get(key)
        if uid and uid not in out:
            out.append(uid)
    return out


def send_message(
    db: Session,
    *,
    team: Team,
    sender: User,
    body: str,
    attachment_version_ids: Iterable[str] | None = None,
    idempotency_key: str | None = None,
    member_user_ids: dict[str, str] | None = None,
) -> ChatMessage:
    mentions = parse_mentions(body, member_user_ids or {})
    msg = ChatMessage(
        id=new_id(),
        team_id=team.id,
        sender_user_id=sender.id,
        seq=0,  # placeholder, set after flush below
        body=body,
        mentions=",".join(mentions),
        created_at=datetime.now(tz=UTC),
    )
    db.add(msg)
    db.flush()
    msg.seq = next_seq(db, team.id)
    db.flush()
    return msg


def get_last_read_seq(db: Session, user_id: str, team_id: str) -> int:
    row = (
        db.query(MessageRead)
        .filter(MessageRead.user_id == user_id, MessageRead.team_id == team_id)
        .one_or_none()
    )
    return row.last_read_seq if row else 0


def mark_read(db: Session, user_id: str, team_id: str, seq: int) -> None:
    row = (
        db.query(MessageRead)
        .filter(MessageRead.user_id == user_id, MessageRead.team_id == team_id)
        .one_or_none()
    )
    if row is None:
        db.add(
            MessageRead(
                id=new_id(),
                user_id=user_id,
                team_id=team_id,
                last_read_seq=seq,
            )
        )
    else:
        if seq > row.last_read_seq:
            row.last_read_seq = seq
    db.flush()


def edit_message(db: Session, *, msg: ChatMessage, actor: User, body: str) -> ChatMessage:
    if msg.sender_user_id != actor.id:
        raise forbidden(code="chat.not_owner", message="Only the author can edit a message.")
    msg.body = body
    msg.edited_at = datetime.now(tz=UTC)
    db.flush()
    return msg


def delete_message(db: Session, *, msg: ChatMessage, actor: User, is_leader: bool) -> ChatMessage:
    if not is_leader and msg.sender_user_id != actor.id:
        raise forbidden(code="chat.not_owner", message="Only the author or leader can delete.")
    msg.deleted_at = datetime.now(tz=UTC)
    msg.body = ""
    db.flush()
    return msg


def list_messages(
    db: Session, team_id: str, *, before_seq: int | None = None, limit: int = 50
) -> list[ChatMessage]:
    q = db.query(ChatMessage).filter(ChatMessage.team_id == team_id)
    if before_seq is not None:
        q = q.filter(ChatMessage.seq < before_seq)
    return q.order_by(ChatMessage.seq.desc()).limit(limit).all()


def unread_count(db: Session, user_id: str, team_id: str) -> int:
    last = get_last_read_seq(db, user_id, team_id)
    return (
        db.query(ChatMessage)
        .filter(
            ChatMessage.team_id == team_id,
            ChatMessage.seq > last,
            ChatMessage.deleted_at.is_(None),
        )
        .count()
    )


def messages_since(db: Session, team_id: str, since_seq: int) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.team_id == team_id, ChatMessage.seq > since_seq)
        .order_by(ChatMessage.seq.asc())
        .all()
    )
