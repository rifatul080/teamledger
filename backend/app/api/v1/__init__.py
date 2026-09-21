"""API v1 router aggregation."""
from __future__ import annotations

from fastapi import APIRouter

# Endpoint modules (filled in Phase 2)
from . import (
    audit,
    auth,
    chat,
    files,
    goals,
    invitations,
    milestones,
    notifications,
    projects,
    schedules,
    scoring,
    tasks,
    teams,
    users,
)

api_v1_router = APIRouter(prefix="/api/v1")

# Mount routers (each module exposes ``router``)
for mod in (
    auth,
    users,
    teams,
    invitations,
    projects,
    goals,
    milestones,
    tasks,
    schedules,
    notifications,
    chat,
    files,
    scoring,
    audit,
):
    if hasattr(mod, "router"):
        api_v1_router.include_router(mod.router)
