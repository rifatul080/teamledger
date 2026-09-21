# Security

This document records the security posture for TeamLedger v1.0.0 and the
controls that must hold for every release.

## Threat model (in scope)

| Threat                                  | Mitigation                                                |
|-----------------------------------------|-----------------------------------------------------------|
| Credential stuffing                     | Per-email + per-IP rate limits on login and reset.        |
| Password breach                         | Argon2id with OWASP-default parameters; never logged.     |
| Session theft via XSS                   | httpOnly cookies; never `document.cookie`.                |
| CSRF                                    | Double-submit cookie; origin check; SameSite=Lax.         |
| Privilege escalation                    | Every endpoint checks `membership`/`role` server-side.    |
| Tampering with author order / scoring   | Immutable snapshots with sha256 hash + audit log.         |
| File-system escape                      | Server-generated paths; archive contents never extracted. |
| Information leakage                     | Audit log leader-only; non-members get 404 (not 403).     |
| Replay                                  | Server-side `seq` on chat; idempotency-key on writes.      |
| MITM in transit                         | TLS termination at the reverse proxy; `Secure` cookies.    |
| Open-redirect / phishing                | Auth codes live only in the DB; never in the URL.         |

## Authentication

* **Argon2id** for password storage (`argon2-cffi` v23+).
* **JWT** access tokens (15-minute TTL by default) in an `HttpOnly` cookie.
* **Refresh tokens** are random 256-bit secrets stored server-side; one is
  valid per (user, family) and rotation revokes the family on reuse.
* **Cookie flags** (production):
  `HttpOnly; SameSite=Lax; Secure; Path=/`.
* **CSRF**: every state-changing endpoint requires `X-CSRF-Token` matching
  the `tl_csrf` cookie. Laravel-style double-submit pattern.
* **CORS**: `CORS_ALLOWED_ORIGINS` is an allowlist; no wildcard in prod.
* **Rate limits** (env-tunable): login 10/min/email, reset 5/min/email,
  IP defaults apply to both. Exceeding returns `429 rate.exceeded`.

## Authorisation

Authorisation is **server-side** on every endpoint. The UI hides actions
purely as a courtesy; the rule engine is in `app/api/deps.py`
(`require_membership`, `require_role`) and is exercised in
`tests/api/test_permission_matrix.py`.

Invariant: every team has **exactly one leader**. Removing the only leader
returns `422`. Transferring demotes the previous leader to a member.

## Input handling

* Request bodies are validated by Pydantic with strict types.
* Strings are length-bounded (e.g. password ≥ 10, reason ≤ 2000).
* Decimal arithmetic in scoring (`app/scoring/`) — never `float`.
* File names are stripped of directory parts; storage paths are server-generated.
* Archive safety (`inspect_zip_safety`) blocks Zip Slip, symlink bombs, and
  any member whose name starts with `/` or `..`.
* Chat body is HTML-escaped on render (`<` → `&lt;` etc.).

## Cryptography

* **Random IDs**: 26-character ULIDs (collision-resistant, time-ordered).
* **Tokens**: `secrets.token_urlsafe(32)` for refresh, `token_hex(32)` for
  password reset, `secrets.choice` over `string.ascii_letters+digits` for
  invite tokens.
* **Hashing**: Argon2id — `time_cost=2`, `memory_cost=64 MiB`,
  `parallelism=2`. Verified in `tests/api/test_auth_login.py`.
* **Snapshot integrity**: SHA-256 over the canonicalised JSON of the
  immutable snapshot row (settings + scores + positions + signature of
  inputs). Visible via the export endpoints.
* **TLS**: terminate at the reverse proxy. Certificates are out-of-band.

## Storage and secrets

* `SECRET_KEY` is read from env; never logged. Defaults only apply in dev.
* All uploads go through `app.storage.base.StoredObject`; nothing is
  rendered server-side. PDFs may be served inline; everything else is
  forced to `Content-Disposition: attachment` with `X-Content-Type-Options: nosniff`.
* Database connection strings are pulled from `DATABASE_URL`; never baked
  into the binary.

## Audit log

`AuditEvent` records every privileged action (membership change, role
change, archive, score adjustment, order finalisation). The log is
**append-only** and exposed leader-only via `GET /teams/{id}/audit`.

## Rate limits

| Endpoint                          | Limit                       |
|-----------------------------------|-----------------------------|
| `POST /auth/login`                | 10/min/email + 30/min/IP    |
| `POST /auth/password/reset`       | 5/min/email                 |
| `POST /auth/password/reset/confirm` | 30/min/IP                 |
| `POST /teams`                     | 10/min/IP                   |
| `POST /teams/{id}/messages`       | 60/min/team                 |

Tunable via env. Excess returns `429 rate.exceeded` with `Retry-After`.

## Logging

* Structured JSON via `app.core.logging`; PII fields (`password`, `token`,
  `set-cookie`) are scrubbed by the formatter.
* No request bodies are logged for `/auth/login`, `/auth/refresh`,
  `/auth/password/reset*`.

## Headers

* `Strict-Transport-Security: max-age=63072000; includeSubDomains` (prod).
* `X-Content-Type-Options: nosniff`.
* `Referrer-Policy: same-origin`.
* `Content-Security-Policy: default-src 'self'; img-src 'self' data:; ...`
  (frontend set; backend only serves JSON).
* CORS preflight is denied for non-allowlisted origins.

## Dependency hygiene

* `bandit -ll` (high+medium) returns 0 issues.
* `pip-audit` is run in CI; failures block release.
* `npm audit --omit=dev` returns 0 high/critical in CI.

## Known limitations

See `docs/known-limitations.md`. The only item in scope here:

* **WebSocket auth** re-reads the `tl_access` query parameter for browser
  compatibility; cookies travel only on the upgrade request. Rotate secrets
  on any suspected compromise.
