"""WebSocket hub: per-team connection registry and broadcast.

Single-process hub for the MVP. Multi-worker scaling needs LISTEN/NOTIFY
(ADR-0004); the local registry here is the in-process branch.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("teamledger.ws")


@dataclass
class Connection:
    ws: WebSocket
    user_id: str
    team_id: str
    last_pong: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


class WebSocketHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_team: dict[str, set[Connection]] = defaultdict(set)

    async def add(self, conn: Connection) -> None:
        async with self._lock:
            self._by_team[conn.team_id].add(conn)

    async def remove(self, conn: Connection) -> None:
        async with self._lock:
            s = self._by_team.get(conn.team_id)
            if s is not None:
                s.discard(conn)
                if not s:
                    self._by_team.pop(conn.team_id, None)

    async def disconnect_user_from_team(self, team_id: str, user_id: str) -> int:
        """Close every socket for a (team, user). Returns the count closed."""
        closed = 0
        async with self._lock:
            connections = list(self._by_team.get(team_id, set()))
        for conn in connections:
            if conn.user_id == user_id:
                try:
                    await conn.ws.close(code=4401)
                except Exception:
                    pass
                await self.remove(conn)
                closed += 1
        return closed

    async def broadcast_json(self, team_id: str, message: dict[str, Any], *, skip_user_id: str | None = None) -> int:
        payload = json.dumps(message, default=str)
        async with self._lock:
            targets = list(self._by_team.get(team_id, set()))
        sent = 0
        for conn in targets:
            if skip_user_id is not None and conn.user_id == skip_user_id:
                continue
            try:
                await conn.ws.send_text(payload)
                sent += 1
            except Exception:
                await self.remove(conn)
        return sent

    def connected_user_ids(self, team_id: str) -> set[str]:
        return {c.user_id for c in self._by_team.get(team_id, set())}

    def team_size(self, team_id: str) -> int:
        return len(self._by_team.get(team_id, set()))


hub = WebSocketHub()
