"""JWT helpers."""
from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

import jwt

from .config import get_settings


def encode_jwt(payload: dict[str, Any], ttl_seconds: int) -> str:
    settings = get_settings()
    now = int(time.time())
    body = {**payload, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(body, settings.secret_key, algorithm="HS256")


def decode_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def hash_token(token: str) -> str:
    """Stable hash for storage of opaque tokens (refresh, reset)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
