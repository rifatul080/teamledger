"""FastAPI application factory."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.v1 import api_v1_router
from .core.clock import SystemClock
from .core.config import get_settings
from .core.errors import AppError
from .db.session import get_engine
from .models import credit  # noqa: F401  - register CRediT categories

log = logging.getLogger("teamledger")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # warm up engine, seed CRediT categories if empty
    get_engine()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="TeamLedger API",
        version="1.0.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-Id",
            "If-None-Match",
        ],
        expose_headers=["X-Request-Id"],
        max_age=600,
    )

    @app.middleware("http")
    async def add_security_headers(
        request: Request, call_next: "Any"
    ) -> "Any":
        response = await call_next(request)
        # Tag every response with a request id so the client can correlate.
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        response.headers["X-Request-Id"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

    @app.middleware("http")
    async def access_log(request: Request, call_next: "Any") -> "Any":
        t0 = time.monotonic()
        response = await call_next(request)
        elapsed = (time.monotonic() - t0) * 1000
        log.info(
            "%s %s -> %s in %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

    @app.exception_handler(AppError)
    async def _app_error_handler(
        request: Request, exc: AppError
    ) -> JSONResponse:
        rid = uuid.uuid4().hex
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": rid,
            },
            headers={"X-Request-Id": rid},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        rid = uuid.uuid4().hex
        code_map = {401: "auth.required", 403: "perm.forbidden", 404: "res.not_found"}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code_map.get(exc.status_code, "http.error"),
                "message": str(exc.detail) if exc.detail else "Error.",
                "details": {},
                "request_id": rid,
            },
            headers={"X-Request-Id": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        rid = uuid.uuid4().hex
        return JSONResponse(
            status_code=422,
            content={
                "code": "req.invalid",
                "message": "Request payload failed validation.",
                "details": {"errors": exc.errors()},
                "request_id": rid,
            },
            headers={"X-Request-Id": rid},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = uuid.uuid4().hex
        log.exception("unhandled exception rid=%s", rid)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal.error",
                "message": "Internal server error.",
                "details": {},
                "request_id": rid,
            },
            headers={"X-Request-Id": rid},
        )

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/time", tags=["health"])
    async def server_time() -> dict[str, str]:
        return {"now": SystemClock().now().isoformat()}

    app.include_router(api_v1_router)
    return app


app = create_app()
