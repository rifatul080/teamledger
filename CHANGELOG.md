# Changelog

All notable changes to TeamLedger are recorded here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2025-01

The first stable release.

### Added

* **Accounts (AUTH-01..07).** Signup with Argon2id passwords, login/logout/refresh,
  profile (`/me`), `display_name` + `timezone` editable, password reset with
  one-time token, `HttpOnly; SameSite=Lax; Secure` cookies, per-email + per-IP
  rate limiting.
* **Teams (TEAM-01..07).** Create team, invite by email (in-app or tokenised link
  for new users), accept invite, remove member, transfer leadership with
  exactly-one-leader invariant, archive, audit log.
* **Projects, goals, milestones, tasks (PROJ-01..10).** `general` / `paper`
  projects with target venue + deadline; participants; goals with rolling
  progress; milestones; tasks with category, weight, due, status flow
  (`todo → in_progress → in_review → needs_rework → done`); self-proposal +
  approve; submit + review by another user; split into multiple tasks.
* **Schedules (SCHED-01..04).** Per-member weekly slots + cap; calendar and
  timeline views; overload warning tied to assignee + cap.
* **Notifications (NOTIF-01..04).** In-app feed; optional email; 3 d / 1 d /
  overdue scheduler; idempotent reminders keyed on
  `(type, task_id, recipient_id, due_bucket)`.
* **Files (FILE-01..07).** Upload, versioning (N+1 on same name), SHA-256,
  content-type sniffing, server-generated paths, archive safety check
  (Zip Slip / symlink bombs), PDF preview inline, ACL.
* **Chat (CHAT-01..09).** Per-team WebSocket, pagination by `seq`, mentions,
  edit + delete, attachments, unread counts, resync on reconnect, HTML
  escape, team isolation (404 for non-members).
* **Scoring & author order (SCORE-01..13).** Pure `Decimal` formula;
  14 CRediT categories with per-project multipliers; leader review quality
  rating 1..5; timeliness bands per project; adjustments with reason; per-
  participant dashboard; suggested + finalised author order; immutable
  snapshot with SHA-256; PDF / CSV / CRediT text exports.
* **Security (SEC-01..06).** Server-side permission checks, append-only
  audit log, pagination, idempotency keys, injected clock, single error
  envelope with `request_id`.

### Testing

* **179 backend tests + 5 frontend tests = 184 total.**
* **Coverage gate = 80%** (currently 81%); scoring module **99%**.
* Property tests via Hypothesis (`tests/property`).
* Static checks: `ruff` 0 issues, `bandit` 0 high/medium, `pip-audit`
  runs in CI.
* One-command runner: `make test-all`.

### Documentation

* `README.md` — quickstart + table of contents.
* `docs/architecture.md` — system diagram, ER diagram, permission matrix.
* `docs/requirements.md` — every requirement has an ID + acceptance criteria.
* `docs/user-guide.md` — full curl walk-through.
* `docs/scoring-methodology.md` — formula + worked example.
* `docs/api.md` — curl examples for every endpoint.
* `docs/security.md` — threat model + controls.
* `docs/deployment.md` — env vars, reverse proxy, capacity planning.
* `docs/testing.md` — layers + traceability + review log.
* `docs/known-limitations.md` — known gaps + workarounds.
* `docs/ASSUMPTIONS.md` — decisions where the spec was open.
* `docs/adr/` — eleven ADRs (FastAPI, ORM, auth, realtime, scheduler,
  frontend, storage, testing, scoring, error envelope, time).
* `PLAN.md` — five-phase plan + actual completion state.

### Operational

* Docker image for the API and the frontend; `docker-compose.yml` for a
  self-contained stack (api + web + db + maildev).
* One-command release flow: tag, push, run migrations on the target DB.

## Versions

| Tag      | Notes                                          |
|----------|------------------------------------------------|
| `v1.0.0` | First stable; freeze on this commit hash       |

## Backwards compatibility

`v1.0.x` is committed to backwards compatibility for the documented
endpoints (`docs/api.md`). Breaking changes will bump the major version
and add a row above with a migration guide.
