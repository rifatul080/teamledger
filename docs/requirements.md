# Requirements

Every requirement has an ID. Acceptance criteria are testable. Tests cite IDs in their docstring or name.

## Accounts — AUTH

- **AUTH-01 Sign up.** A new user can register with email, password (≥ 10 chars, ≥ 1 letter, ≥ 1 digit) and display name. Duplicate email returns 409.
- **AUTH-02 Log in / out.** Login returns httpOnly `access` and `refresh` cookies plus a `tl_csrf` cookie; CSRF required for unsafe verbs. Logout invalidates the refresh token.
- **AUTH-03 Password reset.** "Forgot password" returns 202 in 60s-rate-limited fashion. The reset link contains a one-time token; using it sets a new password and invalidates previous refresh tokens.
- **AUTH-04 Profile.** A user can edit `display_name` and `timezone` (IANA). All timestamps are stored UTC and rendered in the viewer's zone.
- **AUTH-05 Password hashing.** Passwords are hashed with argon2id (parameters from OWASP cheat sheet default).
- **AUTH-06 Security headers / cookies.** Auth cookies are `HttpOnly; SameSite=Lax; Secure` in prod. CORS is allow-listed.
- **AUTH-07 Rate limiting.** Login and reset endpoints have per-IP and per-account caps (see env). Exceeding returns 429.

## Teams & membership — TEAM

- **TEAM-01 Create team.** Any logged-in user can create a team and becomes its leader.
- **TEAM-02 Invite by email.** Leader invites a member by email. Existing user: invitation row appears; non-existing user: a tokenised invite link is generated (TTL from env).
- **TEAM-03 Accept invite.** User accepts and is added as a member.
- **TEAM-04 Remove member.** Leader removes a member. Removed member: access ends immediately (REST 403, WS disconnected); messages/tasks/files/scores retained and labelled "former member".
- **TEAM-05 Transfer leadership.** Leader transfers to a member; demoted leader becomes a member; team still has exactly one leader.
- **TEAM-06 Archive.** Leader archives a team → read-only; mutations return 423 Locked.
- **TEAM-07 Exactly one leader.** Invariant; tested.

## Projects, goals, milestones, tasks — PROJ

- **PROJ-01 Project types.** `general` or `paper`. A paper has target venue, venue kind (`journal`|`conference`), deadline (UTC date).
- **PROJ-02 Participants.** Leader picks participants from the team's members; only participants can be assigned tasks or appear in author order.
- **PROJ-03 Goals.** A goal belongs to a project, has a target date, and reports progress = (sum task progress) / count.
- **PROJ-04 Milestones.** A milestone belongs to a goal, has a due date.
- **PROJ-05 Tasks.** A task belongs to a milestone, has assignee, start, due, est. hours, category (CRediT), weight (1..10), status (todo, in_progress, in_review, needs_rework, done), comments, files. One assignee per task.
- **PROJ-06 Split task.** If two people share work, leader creates two tasks. (UI offers a "split" action that creates a child task with 0 weight.)
- **PROJ-07 Submit for review.** Assignee submits; status becomes `in_review`. First submission timestamp is captured (used for lateness).
- **PROJ-08 Review outcome.** Reviewer accepts (→ `done`, points awarded) or rejects (→ `needs_rework`). Reviewer's identity is not the assignee.
- **PROJ-09 Propose task.** Members can submit a proposed task; leader approves (creates a real task) or declines.
- **PROJ-10 Author order visibility.** A project setting `contrib_visibility` (`leader_only` | `all`) controls dashboard visibility.

## Schedules & notifications — SCHED / NOTIF

- **SCHED-01 Weekly plan.** Leader sets per-member recurring slots and a weekly hour cap.
- **SCHED-02 Calendar.** A team calendar shows tasks/milestones/deadlines for the team and per person.
- **SCHED-03 Timeline.** A timeline view shows the same items over a date range.
- **SCHED-04 Overload warning.** When a member's assigned hours in a week exceed their cap, leader sees a warning (REST 422 with overload detail on task assignment that would exceed).
- **NOTIF-01 In-app.** Members are notified about assignments, review results, mentions, and upcoming/overdue deadlines.
- **NOTIF-02 Deadline reminders.** 3 days before, 1 day before, and on overdue transitions.
- **NOTIF-03 Email optional.** Off by default; mailer is `console` in dev.
- **NOTIF-04 Idempotent scheduler.** Restarting the scheduler never duplicates a reminder for the same `(type, task_id, recipient_id, due_bucket)`.

## Chat — CHAT

- **CHAT-01 WebSocket channel.** One room per team; auth on connect.
- **CHAT-02 Pagination.** Messages loaded in pages (newest-first optional), newest 50 default.
- **CHAT-03 Mentions.** `@display_name` parses to user IDs; mentions notify.
- **CHAT-04 Edit/delete.** Author edits/deletes own message; leader can delete any.
- **CHAT-05 Files.** Attach files from team library.
- **CHAT-06 Unread.** Per-user unread count; resets on view.
- **CHAT-07 Reconnect.** Reconnect resyncs without duplicates or losses (server-assigned monotonic IDs).
- **CHAT-08 Output safety.** Message text is escaped on render; never injected as HTML.
- **CHAT-09 Isolation.** Users in different teams never see each other's messages, even by socket id guessing.

## Files — FILE

- **FILE-01 Upload.** Any current team member may upload. Allowed: PDF, DOC, DOCX, images, datasets, code, zip, tar.gz. Default cap 100 MB.
- **FILE-02 Versioning.** Re-upload of same name in same folder creates version N+1; old kept.
- **FILE-03 Integrity.** Each version stores SHA-256 and uploader.
- **FILE-04 Safe handling.** Storage path is server-generated; original name's directory parts are stripped; content-type sniffed from bytes; downloads always `attachment` + `nosniff`.
- **FILE-05 PDF preview.** PDF served inline; every other type download-only.
- **FILE-06 No server execution.** Archives never extracted server-side.
- **FILE-07 ACL.** Only current team members list/download team files.

## Scoring & author order — SCORE

- **SCORE-01 Formula.** `points = weight × (quality/5) × timeliness × category_multiplier + adjustment`.
- **SCORE-02 Quality.** Reviewer rates 1..5; never self-rated.
- **SCORE-03 Timeliness.** 1.0 on time; 0.9 / 0.75 / 0.5 by lateness band (see ASSUMPTIONS).
- **SCORE-04 CRediT categories.** 14 categories. Per-project multipliers.
- **SCORE-05 Adjustment.** Leader adds manual ± points with a written reason; audit log + dashboard show it.
- **SCORE-06 Dashboard.** Per-participant total, share, by-category, tasks, ratings, lateness, over-time.
- **SCORE-07 Suggestion.** Suggested author order by points desc, tie-broken by name.
- **SCORE-08 Pinned positions.** Leader pins any participant to a fixed position; suggestion fills the rest.
- **SCORE-09 Finalize.** Leader sets final order; per-position note required when differing from suggestion.
- **SCORE-10 Snapshot.** Finalizing writes an immutable snapshot (order, scores, settings, inputs, sha256) exportable as PDF + CSV + CRediT text.
- **SCORE-11 Removed members.** Keep points; can still appear in order.
- **SCORE-12 Pure module.** Scoring arithmetic lives in one module, no DB/IO/clock.
- **SCORE-13 Decimal.** All point math uses `Decimal` or integers — never `float`.

## Security & access control — SEC

- **SEC-01 Server enforcement.** Every endpoint checks membership and role; UI hiding is not enough.
- **SEC-02 Audit log.** Membership, role, deletion, score adjustment, order changes recorded immutably.
- **SEC-03 Pagination.** All list endpoints paginated.
- **SEC-04 Idempotent writes.** Message send and upload endpoints tolerate retries.
- **SEC-05 Injected clock.** All time-dependent code uses the injected clock service.
- **SEC-06 OpenAPI.** Generated at `/api/v1/openapi.json`; one error format.

## UI / accessibility — UI

- **UI-01 Responsive.** Layout works at 375px width.
- **UI-02 Keyboard.** All interactive elements reachable via Tab; visible focus rings.
- **UI-03 Screen reader.** All form fields and buttons have associated `<label>` / `aria-label`.
- **UI-04 States.** Loading / empty / error / offline UI on each screen.
