# ADR-0008 — Testing layers

- **Status:** accepted
- **Context:** Several hundred tests across many layers required.
- **Decision:**
  - Backend unit tests: pytest, hypothesis, table-driven scoring tests.
  - API tests: pytest + httpx AsyncClient against a per-test transaction that rolls back at teardown. Permission matrix read from `docs/architecture.md` and turned into a parametrised set.
  - WebSocket tests: starlette `TestClient` `websocket_connect` with the same auth path as HTTP.
  - File tests: `tmp_path` storage backend; no real disk.
  - Concurrency tests: spin two tasks with `asyncio.gather` against the same row.
  - Schemathesis: from `/api/v1/openapi.json`, runs stateful checks, seeded, with auth header factory.
  - Playwright: end-to-end with two browser contexts per chat scenario.
  - Load: 50 connections × 60s using a small in-house async script, reports p50/p95/p99 latencies.
- **Consequences:**
  - All layers run from `make test` on a clean checkout; one command.
  - Schemathesis is slow; marked `@pytest.mark.schemathesis` so fast smoke runs can skip it.
- **Alternatives considered:**
  - Locust for load — overkill, we measure simple broadcast latency, not throughput under stress.
