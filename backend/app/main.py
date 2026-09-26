"""FastAPI application factory."""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import compile_path

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
        request: Request, call_next: Any
    ) -> Any:
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
    async def access_log(request: Request, call_next: Any) -> Any:
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

    # ----- SEO endpoints -----
    # These MUST be registered before the SPA catch-all below: the catch-all
    # is `/{full_path:path}`, which matches every remaining path, so anything
    # registered after it is unreachable whenever a built SPA exists at
    # ./static — which is always the case inside the Docker image.
    @app.get("/robots.txt", include_in_schema=False)
    async def robots_txt():
        from starlette.responses import PlainTextResponse

        body = (
            "User-agent: *\n"
            "Allow: /\n"
            "Disallow: /dashboard\n"
            "Disallow: /teams\n"
            "Disallow: /projects\n"
            "Disallow: /notifications\n"
            "Disallow: /me\n"
            "Disallow: /api/\n"
        )
        return PlainTextResponse(body, media_type="text/plain")

    @app.get("/sitemap.xml", include_in_schema=False)
    async def sitemap_xml():
        from starlette.responses import Response as _Resp

        base = settings.public_base_url.rstrip("/")
        urls = ["", "/login", "/signup"]
        xml = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        from datetime import UTC, datetime

        for u in urls:
            xml.append(
                "  <url><loc>"
                + f"{base}{u}"
                + "</loc><lastmod>"
                + datetime.now(tz=UTC).date().isoformat()
                + "</lastmod></url>"
            )
        xml.append("</urlset>")
        return _Resp("\n".join(xml), media_type="application/xml")

    # ----- SPA static fallback -----
    # If a built SPA exists at ./static (the docker path), serve it from here.
    # Anything not under /api/ falls through to the SPA's index.html so React
    # Router owns the URL space on the frontend.
    static_dir = (Path(__file__).parent.parent / "static").resolve()
    if static_dir.exists() and (static_dir / "index.html").exists():
        from starlette.staticfiles import StaticFiles

        app.mount(
            "/assets",
            StaticFiles(directory=str(static_dir / "assets")),
            name="spa-assets",
        )

        from starlette.responses import FileResponse

        # Path matchers for the real API routes, derived from the generated
        # OpenAPI schema. The catch-all route below matches *every* path,
        # which would otherwise swallow the 405 that Starlette raises for a
        # wrong-method call to a valid API path (it would answer 404
        # instead). Re-deriving that decision here keeps the documented
        # status codes and error envelope intact — see
        # tests/api/test_security_headers.py::test_error_envelope_shape.
        # (Route objects are opaque in this FastAPI build — included routers
        # are not flattened — so the schema is the reliable source.)
        api_path_matchers: list[tuple[Any, set[str]]] = []
        for api_path, api_ops in app.openapi().get("paths", {}).items():
            if not api_path.startswith("/api/"):
                continue
            api_methods = {
                m.upper()
                for m in api_ops
                if m in {"get", "post", "put", "patch", "delete", "head", "options"}
            }
            if api_methods:
                regex, _, _ = compile_path(api_path)
                api_path_matchers.append((regex, api_methods))

        @app.get("/", include_in_schema=False)
        async def spa_index():
            return FileResponse(static_dir / "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_spa_catch(full_path: str):
            # Don't shadow static assets.
            if full_path.startswith("assets/"):
                return JSONResponse({"error": "not found"}, status_code=404)
            # Never serve the SPA shell for API paths: a known path with the
            # wrong method is a 405, anything else is a 404.
            if full_path.startswith("api/"):
                for regex, methods in api_path_matchers:
                    if regex.match("/" + full_path):
                        raise StarletteHTTPException(
                            status_code=405,
                            detail="Method not allowed for this endpoint.",
                            headers={"Allow": ", ".join(sorted(methods))},
                        )
                return JSONResponse({"error": "not found"}, status_code=404)
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(static_dir / "index.html")
    else:
        # Dev mode — the SPA is served by Vite (which proxies /api to this app).
        pass

    return app


app = create_app()
