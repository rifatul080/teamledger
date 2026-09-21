# ADR-0004 — WebSocket hub inside the FastAPI app, in-memory + Postgres for fan-out

- **Status:** accepted
- **Context:** One chat per team; multiple workers possible; messages must survive restarts; reconnect must not lose or duplicate.
- **Decision:** WebSocket hub lives inside the FastAPI app process. Each connection joins a per-team `set[WebSocket]`. New messages are persisted to Postgres with a monotonic per-team `seq` assigned inside the same transaction. Other workers pick up new rows via a Postgres `LISTEN/NOTIFY` channel and broadcast to their connected sockets. Reconnect uses `?since_seq=N`.
- **Consequences:**
  - Single-process dev works out of the box.
  - Multi-worker prod needs the LISTEN/NOTIFY bridge; documented in deployment notes.
  - Server is the authority on sequence numbers; clients never pick them.
- **Alternatives considered:**
  - Redis pub/sub — adds a runtime dep but removes Postgres LISTEN complexity. Held for ADR later if scale requires.
  - External message broker — overkill at this stage.
