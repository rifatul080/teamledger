"""Auth endpoints — implemented in phase 2."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
