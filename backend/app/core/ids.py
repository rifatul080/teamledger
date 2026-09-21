"""ULID generation helpers."""
from __future__ import annotations

import ulid


def new_id() -> str:
    return str(ulid.new())
