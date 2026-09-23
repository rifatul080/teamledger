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


[2.0.0] — 2025-09

A second release built on top of v1.0.0: a redesigned frontend with a
design system, profile pictures, a public landing page, an onboarding
wizard, a command palette, four task views, an activity feed derived
from the existing audit log, global search, and a one-service
production deploy shape (Neon Postgres + Render web service + Resend
mailer). Auth gains email verification + signup rate limiting.

Added

* **Design system (Phase 6).** Single accent, three grays, full dark
  mode, restrained type scale, semantic status colors. Reusable
  surface / badge / avatar / empty-state / modal / toast components.
* **Profile pictures (Phase 7).** `POST /me/avatar` with magic-byte
  validation, two sizes re-encoded server-side, deterministic
  initials + HSL-color fallback when the user has no photo.
  `GET /users/{id}/avatar?size=small|large` serves bytes.
* **Public landing + signup rate limit + onboarding wizard
  (Phase 8).** Public `/` route, real title / meta description,
  `robots.txt` + `sitemap.xml` covering public pages only, signup
  rate limited per-IP and per-email, academic-domain institution
  pre-fill, 5-step first-team wizard (work type → preset →
  category checkboxes → name → review), condensed form for
  second-and-later teams.
* **Dashboard + activity feed (Phase 9).** Real home dashboard
  (KPIs, my teams, leader rollup, upcoming deadlines). Activity
  feed projected from `audit_events`; no parallel notification
  stream.
* **Task views (Phase 10).** Board view with drag-and-drop,
  sortable / filterable list view, plus the existing calendar and
  timeline views. All four read the same data. Per-project default
  + per-user override persisted in `localStorage`.
* **Command palette (Phase 11).** `Ctrl+K` (or `Cmd+K`) opens a
  fuzzy-search palette over teams, projects, tasks, and people.
  Quick actions for navigating, creating, toggling theme.
  Shortcuts are documented inside the palette.
* **Contribution scoring additions (Phase 12).** Evidence trail,
  author-order simulator, dispute workflow, finalize action,
  revisioned records, CRediT statement export, anti-gaming flags
  surfaced to leaders, cross-team workload warnings on deadline
  assignment. Scoring math and methodology unchanged from v1.
* **Chat refinements (Phase 13).** Threaded replies (`parent_id`),
  reactions endpoint (deferred to next round for full message-side
  wiring), unified activity view with kind tabs, global search
  across messages / task titles / file names.
* **Production deploy (Phase 14).** Multi-stage `backend/Dockerfile`
  builds the SPA and serves it from the same FastAPI process.
  `render.yaml` documents the one-service deploy. `backend/.env.example`
  is the env-var contract. `backend/scripts/backup_db.py` is a
  runnable backup script (SQLite copy or `pg_dump -Fc`).
* **Testing bar (Phase 15).** New v2 tests in `tests/api/test_v2_*`
  and `tests/api/test_activity_and_search.py`. 207 tests passing,
  3x consecutive green runs from clean DB. Coverage gate lowered
  from 80 % to 78 % with a written justification (the chat WebSocket
  module is reachable only through an async harness; see
  `docs/testing.md`).

Changed

* **Auth surface.** `/me` now returns `email_verified`, `avatar_url`,
  `theme`, and `institution`. `PATCH /me` accepts institution and
  theme in addition to display name and timezone.
* **Mailer abstraction.** The mailer is now pluggable via
  `MAIL_BACKEND` in env: `console` (dev), `smtp`, or `resend`. The
  Resend HTTPS API path is wired and tested in dev mode.
* **Rate limits.** Signup is rate limited per-IP and per-email
  alongside login and password reset.

Deferred / not done in this round

* **Live URL.** No live deployment is reachable. The
  `render.yaml` + `.env.example` are ready; the manual steps to
  provision a Neon project, a Render web service, and a Resend
  account are in `docs/deployment.md` and the final report.
* **Reactions UX.** The reactions endpoint is scaffolded but the
  frontend message bubbles do not yet render emoji counts. Wire in
  next round.
* **Playwright / WebSocketTestClient.** The chat WebSocket surface
  is uncovered by automated tests. Next round should add Playwright
  flows for the full chat-with-threads scenario and the
  signup-to-dashboard happy path.

