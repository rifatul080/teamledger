# Known limitations

This page lists gaps and intentional omissions in v1.0.0. Each entry names
the area, the version that closes it (where planned), and the workaround
in the meantime.

## Tests not yet wired

| Area                              | Status                                                                 | Workaround in v1.0.0                              |
|-----------------------------------|------------------------------------------------------------------------|---------------------------------------------------|
| WebSocket layer                   | No automated WS tests; smoke only                                     | Manual chat test in dev, `docs/api.md` curl       |
| Schemathesis fuzzing              | Dependency installed, no test module                                   | Run `pytest -m schemathesis` after wiring         |
| Playwright e2e                    | Config present, no specs                                               | Use the running app + curl examples in user guide |
| Twelve-week paper scenario        | Designed, not scripted                                                | Replay the user-guide flow manually               |
| Load test (≈ 50 users / 60 s)     | Not run                                                                | `ab -n 1000 -c 50` against `/api/v1/health`       |
| Concurrency / race tests          | Partial (rate-limit handling, transfer-leadership guard)              | See `tests/api/test_teams_remove.py`             |

## Features deferred

| Area                  | Status                                                                   | Workaround                                          |
|-----------------------|--------------------------------------------------------------------------|-----------------------------------------------------|
| Pinned positions      | Data model field exists; UI/API not yet exposed                          | Reorder manually before finalising                  |
| S3 storage backend    | Local-only; S3 driver scaffolded (storage base) but not enabled          | Mounted volume under `STORAGE_LOCAL_ROOT`           |
| Email digests         | Mailer is a console stub; no scheduled digest                            | Tail `/var/log/app.log` or the container console    |
| Calendar import       | No external calendar sync                                                | Manual schedule entry                               |
| LDAP / SAML SSO       | Out of scope for v1                                                      | Use email/Argon2 auth                               |

## Operational notes

* **Browsers**: tested against Chrome, Edge, and Firefox. Safari is
  expected to work; if you find an issue, file with a HAR.
* **Mobile**: the UI is responsive at 375 px wide but the chat editor is
  text-only — no rich-text formatting, no image paste.
* **Locales**: timestamps are rendered in the viewer's IANA timezone;
  numbers use the system locale. Currency formatting is not applied
  (points have no currency).
* **Accessibility**: all interactive elements have labels and visible
  focus rings. The chat log is `role="log"` and announces new messages
  via `aria-live="polite"`. There is no screen-reader pass for every
  dialog (WIP).

## Documented trade-offs

* **No `float` in scoring**. This means some rounding happens at display
  time, not before. The exported PDF / CSV carry full precision.
* **Single-leader invariant** is enforced at the service layer. There is
  no "co-leader" role. Use transfer-leader when you need a different
  primary point of contact.
* **Removed members**: messages, tasks, files, and points they earned are
  retained and labelled "former member" — they cannot be erased by the
  leaving party.
* **Snapshot immutability**: finalised author orders cannot be edited. A
  re-finalise creates a new snapshot; older snapshots remain queryable
  by id.

## Reporting a new issue

1. Check `docs/testing.md` § review log for prior related findings.
2. Reproduce against a fresh `make test-all` if possible.
3. Open an issue with:
   * Steps to reproduce.
   * Expected vs actual behaviour.
   * The `request_id` from the error envelope.
   * Output of `python -m scripts.dump_state.py` (a developer-only helper,
     redacted of PII, that serialises the user's view).

The maintainers will triage within 5 working days.
