# Assumptions

This file records reasonable choices the engineer made when the spec left something open. Each entry names the decision, why it was made, and what it implies elsewhere.

## Environment (recorded early)

- **No Docker on the dev machine.** `docker`, `docker compose`, `gh`, and `psql` are not installed. The CI workflow runs the same `docker compose up` flow on GitHub runners, and the application supports a SQLite profile for local quick-start via `make dev-no-docker` / `make seed`. Production deployment targets Postgres per the spec; SQLite is local-only.
- **Python 3.14 is on PATH, the spec targets 3.12.** The Dockerfile pins 3.12. Local tooling uses 3.14 with PEP-604 unions (`X | None`) so type checks pass on both. SQLAlchemy 2 and Pydantic v2 support 3.12/3.14.
- **`gh` CLI not installed.** Publishing relies on git over HTTPS. The exact commands are listed in the publish section; if a credential is cached the agent pushes; otherwise the final report contains a step-by-step using the GitHub web UI or `git push`.
- **No `--add-my-name` for the agent.** As requested, only the configured git user (`sadia / sadiaislamnew2024@gmail.com`) appears in commits. No co-author trailers, no CHANGELOG/PROJECT entries from the agent.

## Functional choices

- **Author order tie-breaker.** Documented rule: alphabetical by display name (case-insensitive, locale-aware UTF-8 sort), then by user ID for stable order. Same tie-breaker is used in CRediT statement text. (ADR-0009)
- **CRediT category multiplier default = 1.0 per category per project.** Spec allows leaders to tune; UI exposes per-project multipliers between 0.0 and 5.0 with two decimals, default 1.00.
- **Timeliness formula.** Piecewise-constant with three bands controlled by project settings:
  - submitted at or before due date → 1.0
  - submitted ≤ 2 days late → 0.9
  - submitted ≤ 7 days late → 0.75
  - submitted > 7 days late → 0.5
  Band thresholds are numeric days stored on the project (`timeliness_band_*_days`), defaulting to {2, 7}. Out-of-band adjustability is documented in `docs/scoring-methodology.md`.
- **Reviewer for tasks owned by the leader.** If the project has no named reviewer, the task's review is the mean quality rating from at least two other participants; else the mean of available reviews for that task. The averaging happens at acceptance time and the mean is stored on the task (stable, not recomputed later).
- **Duplicate signups with the same email** are blocked: signup requires a fresh email per account. A user with an existing email is told the email is in use (no enumeration of existence, but the message is uniform).
- **Open chat removal.** Per spec, removing a member closes their sockets *now*. Implemented via the auth dependency on `ws_connect`: each tick checks membership and disconnects any dropped session. Also implemented as a server-side `kick` event after REST remove. Belt and braces.
- **CSS for email** uses MJML-free inline HTML with a text part for `text/html` and `text/plain`; mailer is `console` in dev, `smtp` in prod.
- **Idempotent notifications** are keyed on `(notification_type, task_id, recipient_id, due_bucket)` so re-firing the scheduler cannot duplicate a "3 days left" reminder for the same task in the same window.
- **Pagination.** `page` + `page_size` on every list endpoint, default page_size=50, max 200, returns `{items, total, page, page_size}`.
- **Error envelope.** RFC-7807-ish `{code, message, details?, request_id}` returned for all non-2xx JSON. HTTP 401 for missing auth, 403 for wrong role/team, 404 for not found or hidden resource (no enumeration).
- **File storage interface.** `StorageBackend` with `LocalDiskStorage` implementation, path computed as `teams/{team_id}/{yyyy}/{mm}/{ulid}_{safe_name}`. Detected content type via `python-magic` (libmagic) or a fallback that reads the first 4 bytes when libmagic is unavailable. PDF preview served inline with `Content-Disposition: inline; filename="..."` for `application/pdf` only.
- **No server-side archive extraction.** Archives are stored verbatim; downloads don't unpack. Filenames inside archives are checked at download-time for browser safety but server never executes them.
- **Security headers.** `Referrer-Policy: same-origin`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Permissions-Policy` minimal, `Content-Security-Policy` strict (frontend assets via nonce).
- **CSRF.** Double-submit cookie (`tl_csrf`) sent as `X-CSRF-Token` on unsafe verbs; refreshed on login.
- **Audit log.** Append-only `audit_events` table; one row per membership/role/score/order change.

## Repository

- Project lives at `teamledger` (lowercase). If the name is taken on GitHub the agent uses `teamledger-app` (also documented in this file).
- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Subject line ≤ 72 chars.
- No force-pushes, no history rewrites after first push.

## v2 (Phase 6+)
Same backend serves the SPA + static assets. Resend for mail. Neon for Postgres. Render free web service for backend. Signup rate limit per-IP and per-email.
Things not done in this run: live URL (requires Render+Neon accounts), live email (requires Resend API key), domain purchase. Manual steps in the final report.
