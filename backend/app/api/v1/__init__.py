"""API v1 router aggregation."""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    activity,
    audit,
    auth,
    chat,
    files,
    goals,
    health,
    invitations,
    milestones,
    notifications,
    projects,
    schedules,
    scoring,
    search,
    tasks,
    teams,
    users,
)

api_v1_router = APIRouter(prefix="/api/v1")

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
    activity,
    search,
    health,
):
    if hasattr(mod, "router"):
        api_v1_router.include_router(mod.router)
