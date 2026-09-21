"""Common error envelope and HTTPException helpers."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status


class AppError(HTTPException):
    """HTTP error with a stable machine code.

    Maps to the canonical envelope: ``{"code", "message", "details", "request_id"}``.
    """

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.request_id = uuid.uuid4().hex


def unauthorized(message: str = "Authentication required.", code: str = "auth.required") -> AppError:
    return AppError(status_code=status.HTTP_401_UNAUTHORIZED, code=code, message=message)


def forbidden(message: str = "Forbidden.", code: str = "perm.forbidden") -> AppError:
    return AppError(status_code=status.HTTP_403_FORBIDDEN, code=code, message=message)


def not_found(message: str = "Not found.", code: str = "res.not_found") -> AppError:
    return AppError(status_code=status.HTTP_404_NOT_FOUND, code=code, message=message)


def conflict(message: str, code: str = "res.conflict") -> AppError:
    return AppError(status_code=status.HTTP_409_CONFLICT, code=code, message=message)


def validation(message: str, code: str = "req.invalid", details: dict[str, Any] | None = None) -> AppError:
    return AppError(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, code=code, message=message, details=details)


def locked(message: str, code: str = "res.locked") -> AppError:
    return AppError(status_code=status.HTTP_423_LOCKED, code=code, message=message)


def rate_limited(message: str = "Too many requests.") -> AppError:
    return AppError(status_code=status.HTTP_429_TOO_MANY_REQUESTS, code="rate.exceeded", message=message)
