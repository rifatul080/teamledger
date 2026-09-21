# API Reference

Base URL: `http://localhost:8000/api/v1`

OpenAPI / Swagger: `http://localhost:8000/docs` (interactive)
OpenAPI JSON: `http://localhost:8000/api/v1/openapi.json`

All authenticated requests require two cookies:

* `tl_access` — short-lived JWT (15 min default).
* `tl_csrf` — opaque token used for unsafe verbs (POST/PUT/PATCH/DELETE).

All unsafe-verb requests must also send the header:

```
X-CSRF-Token: <value of tl_csrf cookie>
```

## Error envelope

Every error returns the same JSON envelope:

```json
{
  "code": "team.not_found",
  "message": "Team not found.",
  "details": { "team_id": "abc123" },
  "request_id": "01HMR..."
}
```

| HTTP | code prefix       | meaning                                  |
|------|-------------------|------------------------------------------|
| 400  | `req.invalid`     | Validation failure (schema / business)   |
| 401  | `auth.required`   | Missing or invalid auth                  |
| 403  | `auth.forbidden`  | Authenticated but unauthorised           |
| 404  | `<thing>.not_found` | Target id unknown                       |
| 409  | `<thing>.conflict`| Idempotency / uniqueness                 |
| 422  | `req.invalid`     | Body / query validation                  |
| 429  | `rate.exceeded`   | Rate limit hit                           |

## Auth

### `POST /auth/signup`

```bash
curl -sS -X POST http://localhost:8000/api/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "ada@example.org",
    "password": "Password1Demo",
    "display_name": "Ada",
    "timezone": "Europe/London"
  }'
# 201 Created -> {"id":"...","email":...,"display_name":...,"timezone":...}
```

### `POST /auth/login`

```bash
curl -sS -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.org","password":"Password1Demo"}'
# 200 OK, sets tl_access + tl_refresh + tl_csrf cookies
```

### `POST /auth/refresh`

```bash
curl -sS -b cookies.txt -c cookies.txt \
  -X POST http://localhost:8000/api/v1/auth/refresh
```

### `POST /auth/logout`

```bash
curl -sS -b cookies.txt -X POST http://localhost:8000/api/v1/auth/logout
# 204 No Content; clears cookies + invalidates refresh token
```

### `GET /me`

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/me
```

### `PATCH /me`

```bash
curl -sS -b cookies.txt -X PATCH http://localhost:8000/api/v1/me \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $(grep tl_csrf cookies.txt | awk '{print $7}')" \
  -d '{"display_name": "Ada Lovelace", "timezone": "UTC"}'
```

### `POST /auth/password/reset`

```bash
curl -sS -X POST http://localhost:8000/api/v1/auth/password/reset \
  -H 'Content-Type: application/json' -d '{"email":"ada@example.org"}'
# 202 Accepted; dev returns the ticket token in the body
```

### `POST /auth/password/reset/confirm`

```bash
curl -sS -X POST http://localhost:8000/api/v1/auth/password/reset/confirm \
  -H 'Content-Type: application/json' \
  -d '{"token":"<ticket>","new_password":"NewPassword1"}'
# 204 No Content
```

## Teams

### `POST /teams`

```bash
curl -sS -b cookies.txt -X POST http://localhost:8000/api/v1/teams \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"name":"Adaptive Systems Lab"}'
```

### `GET /teams`

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/teams
# 200 OK -> Team list for the current user
```

### `POST /teams/{team_id}/invitations`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"email":"newbie@example.org"}' \
  http://localhost:8000/api/v1/teams/$TEAM/invitations
```

### `POST /invitations/{token}/accept`

```bash
curl -sS -b cookies.txt -X POST \
  -H "X-CSRF-Token: $CSRF" \
  http://localhost:8000/api/v1/invitations/$TOKEN/accept
```

### `POST /teams/{team_id}/transfer-leader`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{\"new_leader_user_id\":\"$USER_ID\"}" \
  http://localhost:8000/api/v1/teams/$TEAM/transfer-leader
```

### `POST /teams/{team_id}/archive`

```bash
curl -sS -b cookies.txt -X POST \
  -H "X-CSRF-Token: $CSRF" \
  http://localhost:8000/api/v1/teams/$TEAM/archive
```

### `GET /teams/{team_id}/audit` (leader only)

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/teams/$TEAM/audit
# 200 OK -> {"items":[{action, subject_kind, subject_id, actor_user_id, at, payload}, ...]}
```

## Projects, goals, milestones, tasks

### `GET /credit-categories`

```bash
curl -sS http://localhost:8000/api/v1/credit-categories
# 200 OK -> [{"code":"software","label":"Software"}, ...] (public)
```

### `POST /teams/{team_id}/projects`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{
    "kind":"paper",
    "name":"Latent Margins",
    "target_venue":"TMLR",
    "venue_kind":"journal",
    "submission_deadline":"2026-09-30",
    "contrib_visibility":"all",
    "participant_user_ids":["'$USER_A'","'$USER_B'"]
  }' \
  http://localhost:8000/api/v1/teams/$TEAM/projects
```

### `POST /projects/{project_id}/participants`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{\"user_id\":\"$USER_ID\"}" \
  http://localhost:8000/api/v1/projects/$PROJECT/participants
```

### `PUT /projects/{project_id}/multipliers`

```bash
curl -sS -b cookies.txt -X PUT \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '[{"category_code":"software","multiplier":"1.25"}]' \
  http://localhost:8000/api/v1/projects/$PROJECT/multipliers
```

### `PUT /projects/{project_id}/timeliness`

```bash
curl -sS -b cookies.txt -X PUT \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{
    "on_time_band_days":0,"mild_band_days":2,"medium_band_days":7,
    "late_mild":"0.9","late_medium":"0.75","late_severe":"0.5"
  }' \
  http://localhost:8000/api/v1/projects/$PROJECT/timeliness
```

### `POST /goals` and `POST /goals/{goal_id}/milestones`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{\"project_id\":\"$PROJECT\",\"title\":\"Reach SoTA\",\"target_date\":\"2026-12-31\"}" \
  http://localhost:8000/api/v1/goals

curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"title":"Ablations","due_date":"2026-06-30"}' \
  http://localhost:8000/api/v1/goals/$GOAL/milestones
```

### `POST /tasks`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{
    \"milestone_id\":\"$MILESTONE\",
    \"assignee_user_id\":\"$USER_A\",
    \"title\":\"Run baseline\",
    \"category_code\":\"software\",
    \"weight\":5,
    \"est_hours\":4,
    \"start_date\":\"2026-02-01\",\"due_date\":\"2026-02-15\"
  }" http://localhost:8000/api/v1/tasks
```

### `POST /tasks/{task_id}/submit` and `/review`

```bash
# Assignee submits
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"note":"ready for review"}' http://localhost:8000/api/v1/tasks/$TASK/submit

# Reviewer (not the assignee) accepts with a quality score 1..5
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"decision":"accept","quality":4}' http://localhost:8000/api/v1/tasks/$TASK/review
```

### `POST /tasks/{task_id}/approve-proposal`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{}" http://localhost:8000/api/v1/tasks/$TASK/approve-proposal
```

## Files

### `POST /teams/{team_id}/files` (multipart upload)

```bash
curl -sS -b cookies.txt -X POST \
  -H "X-CSRF-Token: $CSRF" \
  -F "file=@./paper.pdf" \
  http://localhost:8000/api/v1/teams/$TEAM/files
```

### `GET /teams/{team_id}/files/{file_id}/download`

```bash
curl -sS -b cookies.txt -OJ http://localhost:8000/api/v1/teams/$TEAM/files/$FILE/download
```

### `POST /teams/{team_id}/files/check-archive`

```bash
# body is the raw archive bytes; returns {"safe":bool,"reasons":[...]}
curl -sS -b cookies.txt -X POST \
  -H "Content-Type: application/zip" -H "X-CSRF-Token: $CSRF" \
  --data-binary @./submission.zip \
  http://localhost:8000/api/v1/teams/$TEAM/files/check-archive
```

## Chat

### `POST /teams/{team_id}/messages`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"body":"Hi @everyone — submit drafts by Friday."}' \
  http://localhost:8000/api/v1/teams/$TEAM/messages
```

### `GET /teams/{team_id}/messages?before_seq=N&limit=50`

```bash
curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/messages?limit=20"
```

### WebSocket: `/teams/{team_id}/chat`

```text
ws://localhost:8000/api/v1/teams/$TEAM/chat?access=<tl_access value>
Server sends {type:"message", id, team_id, sender_user_id, seq, body, mentions, ...} for every new message.
Resync with `?before_seq=N` if a client reconnects.
```

## Schedules

```bash
curl -sS -b cookies.txt -X PUT \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{
    "slots":[{"weekday":1,"start_minute":540,"end_minute":1020,"note":null}],
    "weekly_cap_hours":25
  }' \
  http://localhost:8000/api/v1/teams/$TEAM/schedules?user_id=$USER_ID

curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/calendar?week_start=2026-01-05"
curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/timeline?start=2026-01-05&end=2026-01-12"
curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/overload?week_start=2026-01-05"
```

## Scoring

### `GET /projects/{project_id}/score`

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/projects/$PROJECT/score
# 200 OK -> ScoreRead (totals, per-participant breakdowns, suggested_order)
```

### `POST /projects/{project_id}/adjustments` (leader)

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{\"user_id\":\"$USER\",\"delta\":\"2.5\",\"reason\":\"extra review\"}" \
  http://localhost:8000/api/v1/projects/$PROJECT/adjustments
```

### `POST /projects/{project_id}/author-order/finalize`

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{
    \"positions\":[
      {\"position\":1,\"user_id\":\"$USER_A\"},
      {\"position\":2,\"user_id\":\"$USER_B\"}
    ]
  }" http://localhost:8000/api/v1/projects/$PROJECT/author-order/finalize
# 201 Created -> {"snapshot_id":"..."} (use as ?snapshot_id=... for exports)
```

### Exports

```bash
curl -sS -b cookies.txt -OJ "http://localhost:8000/api/v1/projects/$PROJECT/author-order/export.pdf?snapshot_id=$SNAP"
curl -sS -b cookies.txt    "http://localhost:8000/api/v1/projects/$PROJECT/author-order/export.csv?snapshot_id=$SNAP"
curl -sS -b cookies.txt    "http://localhost:8000/api/v1/projects/$PROJECT/author-order/statement.txt?snapshot_id=$SNAP"
```

## Notifications

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/notifications
curl -sS -b cookies.txt http://localhost:8000/api/v1/notifications/unread-count
curl -sS -b cookies.txt -X POST -H "X-CSRF-Token: $CSRF" \
  http://localhost:8000/api/v1/notifications/read-all
```

## Versioning, idempotency, and pagination

* All list endpoints accept `limit` and an opaque `cursor` (when applicable) or
  `before_seq` (chat). Defaults match the documented bounds.
* `POST /teams/{team_id}/messages` accepts an optional `Idempotency-Key`
  header; replays return the original record.
* Uploads are deduped on `(team_id, folder, name)` and create `version=N+1`.
