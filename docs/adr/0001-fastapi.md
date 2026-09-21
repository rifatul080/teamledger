# ADR-0001 — FastAPI as the backend framework

- **Status:** accepted
- **Context:** backend needs typed routes, OpenAPI, WebSocket, dependency injection, Pydantic models.
- **Decision:** FastAPI 0.115+.
- **Consequences:**
  - Strong OpenAPI 3.1 generation (used by Schemathesis and frontend codegen).
  - Dependency-injection makes the auth/role matrix trivial to enforce across every endpoint.
  - WebSockets are first-class and share event loops with HTTP — simpler than running a separate ASGI app.
  - Pydantic v2 keeps a single source of truth for request/response models.
- **Alternatives considered:**
  - Django + DRF — too much ceremony, no first-class WS for per-team rooms.
  - Flask — would require Flask-Smorest + manual WS wiring; losing OpenAPI auto-generation costs us Schemathesis coverage.
