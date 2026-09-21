"""Chat: REST for paging, WebSocket for real-time."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ...api.deps import current_user, get_db, require_membership
from ...core.errors import not_found, validation
from ...core.tokens import decode_jwt
from ...db.session import get_sessionmaker
from ...models.message import ChatMessage
from ...models.team import Team
from ...models.user import User
from ...realtime.hub import Connection, hub
from ...schemas.chat import MessageEdit, MessageRead, MessageSend
from ...services import chat_service, team_service

log = logging.getLogger("teamledger.chat")

router = APIRouter(tags=["chat"])


def _serialize(msg: ChatMessage) -> dict:
    return {
        "type": "message",
        "id": msg.id,
        "team_id": msg.team_id,
        "sender_user_id": msg.sender_user_id,
        "seq": msg.seq,
        "body": msg.body,
        "mentions": [m for m in (msg.mentions or "").split(",") if m],
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "deleted": msg.deleted_at is not None,
        "created_at": msg.created_at.isoformat(),
    }


@router.get("/teams/{team_id}/messages", response_model=list[MessageRead])
def list_messages(
    team_id: str,
    before_seq: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[MessageRead]:
    require_membership(team_id, db, user.id)
    rows = chat_service.list_messages(db, team_id, before_seq=before_seq, limit=limit)
    return [_to_read(m) for m in rows]


def _to_read(msg: ChatMessage) -> MessageRead:
    return MessageRead(
        id=msg.id,
        team_id=msg.team_id,
        sender_user_id=msg.sender_user_id,
        seq=msg.seq,
        body=msg.body,
        mentions=[m for m in (msg.mentions or "").split(",") if m],
        edited_at=msg.edited_at,
        deleted=msg.deleted_at is not None,
        created_at=msg.created_at,
    )


@router.post("/teams/{team_id}/messages", response_model=MessageRead, status_code=201)
def send_message(
    payload: MessageSend,
    team_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MessageRead:
    _ = require_membership(team_id, db, user.id)
    team = db.get(Team, team_id)
    if team.archived:
        raise validation("Team is archived.", code="team.archived")
    members = team_service.list_members(db, team_id)
    name_map = {u.id: u.display_name for u, _ in members}
    msg = chat_service.send_message(
        db,
        team=team,
        sender=user,
        body=payload.body,
        attachment_version_ids=payload.attachment_version_ids,
        member_user_ids=name_map,
    )
    db.commit()
    # Broadcast in background
    _ = asyncio.create_task(
        hub.broadcast_json(team_id, {"type": "message", **{
            "id": msg.id, "team_id": msg.team_id, "sender_user_id": msg.sender_user_id,
            "seq": msg.seq, "body": msg.body, "mentions": [m for m in (msg.mentions or "").split(",") if m],
            "edited_at": None, "deleted": False, "created_at": msg.created_at.isoformat(),
        }})
    )
    return _to_read(msg)


@router.patch("/teams/{team_id}/messages/{msg_id}", response_model=MessageRead)
def edit_message(
    team_id: str,
    msg_id: str,
    payload: MessageEdit,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MessageRead:
    _ = require_membership(team_id, db, user.id)
    msg = db.get(ChatMessage, msg_id)
    if msg is None or msg.team_id != team_id:
        raise not_found(code="chat.not_found")
    chat_service.edit_message(db, msg=msg, actor=user, body=payload.body)
    db.commit()
    _ = asyncio.create_task(hub.broadcast_json(team_id, _serialize(msg)))
    return _to_read(msg)


@router.delete("/teams/{team_id}/messages/{msg_id}", status_code=204)
def delete_message(
    team_id: str,
    msg_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    m = require_membership(team_id, db, user.id)
    msg = db.get(ChatMessage, msg_id)
    if msg is None or msg.team_id != team_id:
        raise not_found(code="chat.not_found")
    chat_service.delete_message(db, msg=msg, actor=user, is_leader=(m.role == "leader"))
    db.commit()
    _ = asyncio.create_task(hub.broadcast_json(team_id, _serialize(msg)))

@router.get("/teams/{team_id}/unread")
def unread(
    team_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_membership(team_id, db, user.id)
    return {"unread": chat_service.unread_count(db, user.id, team_id)}


@router.post("/teams/{team_id}/read")
def mark_read(
    team_id: str,
    seq: int = Query(..., ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_membership(team_id, db, user.id)
    chat_service.mark_read(db, user.id, team_id, seq)
    db.commit()
    return {"last_read_seq": chat_service.get_last_read_seq(db, user.id, team_id)}


# ---------------------------------------------------------------------------
# WebSocket


async def _authenticate_ws(websocket: WebSocket) -> tuple[User, Team] | tuple[None, None]:
    token = websocket.cookies.get("tl_access") or websocket.query_params.get("access_token")
    if not token:
        await websocket.close(code=4401)
        return None, None
    try:
        payload = decode_jwt(token)
    except Exception:
        await websocket.close(code=4401)
        return None, None
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        await websocket.close(code=4401)
        return None, None
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=4401)
            return None, None
        team_id = websocket.path_params.get("team_id")
        team = db.get(Team, team_id)
        if team is None:
            await websocket.close(code=4404)
            return None, None
        m = (
            db.query(__import__("app.models.membership", fromlist=["Membership"]).Membership)
            .filter(
                __import__("app.models.membership", fromlist=["Membership"]).Membership.user_id == user.id,
                __import__("app.models.membership", fromlist=["Membership"]).Membership.team_id == team_id,
                __import__("app.models.membership", fromlist=["Membership"]).Membership.removed_at.is_(None),
            )
            .one_or_none()
        )
        if m is None:
            await websocket.close(code=4403)
            return None, None
        return user, team


@router.websocket("/teams/{team_id}/chat")
async def chat_socket(websocket: WebSocket, team_id: str) -> None:
    user, team = await _authenticate_ws(websocket)
    if user is None or team is None:
        return
    await websocket.accept()
    conn = Connection(ws=websocket, user_id=user.id, team_id=team_id)
    await hub.add(conn)
    SessionLocal = get_sessionmaker()
    try:
        # Initial sync
        with SessionLocal() as db:
            since = websocket.query_params.get("last_seq")
            since_i = int(since) if since and since.isdigit() else None
            messages = (
                chat_service.messages_since(db, team_id, since_i or 0)
                if since_i is not None
                else chat_service.list_messages(db, team_id, limit=50)
            )
        await websocket.send_json(
            {
                "type": "sync",
                "messages": [_serialize(m) for m in messages],
                "server_time": datetime.now(tz=UTC).isoformat(),
            }
        )
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                await websocket.send_json({"type": "error", "code": "chat.bad_payload"})
                continue
            kind = data.get("type")
            if kind == "send":
                body = (data.get("body") or "").strip()
                if not body:
                    await websocket.send_json({"type": "error", "code": "chat.empty"})
                    continue
                with SessionLocal() as db:
                    members = team_service.list_members(db, team_id)
                    name_map = {u.id: u.display_name for u, _ in members}
                    t = db.get(Team, team_id)
                    msg = chat_service.send_message(
                        db, team=t, sender=user, body=body,
                        attachment_version_ids=data.get("attachment_version_ids"),
                        idempotency_key=data.get("client_msg_id"),
                        member_user_ids=name_map,
                    )
                    db.commit()
                payload = _serialize(msg)
                await hub.broadcast_json(team_id, payload)
            elif kind == "edit":
                mid = data.get("id")
                body = (data.get("body") or "").strip()
                with SessionLocal() as db:
                    msg = db.get(ChatMessage, mid)
                    if msg is None or msg.team_id != team_id:
                        await websocket.send_json({"type": "error", "code": "chat.not_found"})
                        continue
                    chat_service.edit_message(db, msg=msg, actor=user, body=body)
                    db.commit()
                    payload = _serialize(msg)
                await hub.broadcast_json(team_id, payload)
            elif kind == "delete":
                mid = data.get("id")
                with SessionLocal() as db:
                    msg = db.get(ChatMessage, mid)
                    if msg is None or msg.team_id != team_id:
                        await websocket.send_json({"type": "error", "code": "chat.not_found"})
                        continue
                    is_leader = _is_leader_ws(db, team_id, user.id)
                    chat_service.delete_message(db, msg=msg, actor=user, is_leader=is_leader)
                    db.commit()
                    payload = _serialize(msg)
                await hub.broadcast_json(team_id, payload)
            elif kind == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "error", "code": "chat.unknown_type"})
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws error")
    finally:
        await hub.remove(conn)


def _is_leader_ws(db: Session, team_id: str, user_id: str) -> bool:
    from ...models.membership import Membership

    m = (
        db.query(Membership)
        .filter(
            Membership.team_id == team_id,
            Membership.user_id == user_id,
            Membership.removed_at.is_(None),
        )
        .one_or_none()
    )
    return m is not None and m.role == "leader"
