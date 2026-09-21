# ADR-0005 — APScheduler for in-process scheduling

- **Status:** accepted
- **Context:** Spec requires APScheduler and idempotent reminders.
- **Decision:** APScheduler `BackgroundScheduler` running inside the API process for dev and small prod. Idempotency enforced by a `notification_keys` table with `(type, task_id, recipient_id, due_bucket)` as a unique key. Two jobs:
  - `deadline_reminder_3d` once per hour
  - `deadline_reminder_1d` once per hour
  - `overdue_sweep` once per hour
  All three query the clock via the injected `Clock` interface.
- **Consequences:**
  - In-process scheduler survives restarts (jobs re-fire next tick) but the unique-key table guarantees no duplicate notifications.
  - Horizontal scale: each replica's scheduler inserts would conflict on the unique key — by design, the second replica's `INSERT` returns `IntegrityError` and the row is dropped.
- **Alternatives considered:**
  - Celery beat — heavier; rejected for scope.
  - Cron + `CLI` runner — adds ops surface for an MVP.
