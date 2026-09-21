# ADR-0010 — One error envelope, request id, problem-detail style

- **Status:** accepted
- **Context:** Spec says one error format.
- **Decision:** All non-2xx JSON responses use:
  ```json
  { "code": "auth.invalid_credentials", "message": "Invalid email or password.", "details": {...}, "request_id": "..." }
  ```
  - `code` is stable, dotted, machine-readable.
  - `request_id` correlates to a server-side log line and to a header (`X-Request-Id`).
  - HTTP status carries the broad category; `code` carries the precise reason.
  - WebSocket errors use the same envelope on a control message.
- **Consequences:**
  - Frontend can switch on `code` without parsing English.
  - Easier to write Schemathesis assertions keyed on status + code.
- **Alternatives considered:**
  - Pure RFC-7807 `application/problem+json` — closer to spec, but lacks the stable machine code; we add `code` to it.
