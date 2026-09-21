"""Password hashing primitives."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    try:
        _hasher.verify(stored_hash, plain)
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def password_strength_ok(plain: str) -> bool:
    if len(plain) < 10:
        return False
    has_letter = any(c.isalpha() for c in plain)
    has_digit = any(c.isdigit() for c in plain)
    return has_letter and has_digit
