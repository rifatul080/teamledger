# User guide

This walk-through takes you from a fresh install to a finalised paper with
a published author order. The same flow is automated in
`backend/tests/api/test_tasks.py` and `backend/tests/api/test_scoring.py`.

## 0. Seed demo data

```bash
cd backend
python -m scripts.seed_demo
```

This creates two teams ("Adaptive Systems Lab" and "Probabilistic Vision
Lab") with five participants each, one active paper per team, and a
12-week milestone plan. Use those accounts to explore the UI.

## 1. Sign up and create a team

```bash
curl -sS -X POST http://localhost:8000/api/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{
    "email":"ada@example.org",
    "password":"Password1Demo",
    "display_name":"Ada",
    "timezone":"Europe/London"
  }'

curl -sS -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.org","password":"Password1Demo"}'

curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://localhost:8000/api/v1/teams \
  -d '{"name":"Adaptive Systems Lab"}'
```

The creator becomes the **leader** — the only role allowed to add
projects, invite members, set schedule caps, and finalise the author
order.

## 2. Invite teammates

```bash
curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://localhost:8000/api/v1/teams/$TEAM/invitations \
  -d '{"email":"babbage@example.org"}'
```

Two cases:

* **User exists**: the invitation row appears in their `/teams` page.
* **User does not exist**: a tokenised link is generated. In development
  the token is returned in the response so you can test without SMTP.

The invitee accepts:

```bash
curl -sS -b cookies.txt -c cookies.txt \
  -H "X-CSRF-Token: $CSRF" \
  -X POST http://localhost:8000/api/v1/invitations/$TOKEN/accept
```

## 3. Create a paper project

```bash
curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://localhost:8000/api/v1/teams/$TEAM/projects \
  -d "{
    \"kind\":\"paper\",
    \"name\":\"Latent Margins\",
    \"target_venue\":\"TMLR\",
    \"venue_kind\":\"journal\",
    \"submission_deadline\":\"2026-09-30\",
    \"contrib_visibility\":\"all\",
    \"participant_user_ids\":[\"$ADA\",\"$BABBAGE\"]
  }"
```

Pick a **reviewer** (different from any participant) so the project has
someone to assign reviews to:

```bash
curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X PATCH http://localhost:8000/api/v1/projects/$PROJECT \
  -d "{\"reviewer_user_id\":\"$REVIEWER_ID\"}"
```

## 4. Set category multipliers and timeliness bands (optional)

```bash
curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X PUT http://localhost:8000/api/v1/projects/$PROJECT/multipliers \
  -d '[{"category_code":"software","multiplier":"1.25"}]'

curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X PUT http://localhost:8000/api/v1/projects/$PROJECT/timeliness \
  -d '{
    "on_time_band_days":0, "mild_band_days":2, "medium_band_days":7,
    "late_mild":"0.9", "late_medium":"0.75", "late_severe":"0.5"
  }'
```

See **[docs/scoring-methodology.md](scoring-methodology.md)** for the
default values.

## 5. Goals, milestones, tasks

```bash
# Goal
GID=$(curl -sS -b cookies.txt -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" -X POST http://localhost:8000/api/v1/goals \
  -d "{\"project_id\":\"$PROJECT\",\"title\":\"Reach SoTA\",\"target_date\":\"2026-12-31\"}" \
  | jq -r .id)

# Milestone
MID=$(curl -sS -b cookies.txt -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" -X POST http://localhost:8000/api/v1/goals/$GID/milestones \
  -d '{"title":"Ablations","due_date":"2026-06-30"}' | jq -r .id)

# Task
TID=$(curl -sS -b cookies.txt -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $CSRF" -X POST http://localhost:8000/api/v1/tasks \
  -d "{
    \"milestone_id\":\"$MID\",
    \"assignee_user_id\":\"$ADA\",
    \"title\":\"Run baseline\",
    \"category_code\":\"software\",
    \"weight\":5,
    \"est_hours\":4,
    \"start_date\":\"2026-02-01\",\"due_date\":\"2026-02-15\"
  }" | jq -r .id)
```

### Submit + review cycle

The assignee submits work, the reviewer (not the assignee) rates it.

```bash
curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://localhost:8000/api/v1/tasks/$TID/submit \
  -d '{"note":"baseline runs uploaded"}'

curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://localhost:8000/api/v1/tasks/$TID/review \
  -d '{"decision":"accept","quality":4}'
```

If the reviewer **rejects**, the task goes to `needs_rework`. The
assignee resubmits with `submit` again; the loop continues.

If the assignee **proposes** the task themselves, the leader approves:

```bash
curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://localhost:8000/api/v1/tasks/propose \
  -d "{ ... task payload ... }"

# Later, leader approves:
curl -sS -b cookies.txt -c cookies.txt \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -X POST http://localhost:8000/api/v1/tasks/$PROPOSED_TID/approve-proposal \
  -d '{}'
```

## 6. Files

```bash
curl -sS -b cookies.txt -X POST -H "X-CSRF-Token: $CSRF" \
  -F "file=@./paper.pdf" \
  http://localhost:8000/api/v1/teams/$TEAM/files

# Re-uploading the same name creates version N+1; old versions are kept.
curl -sS -b cookies.txt http://localhost:8000/api/v1/teams/$TEAM/files
curl -sS -b cookies.txt -OJ http://localhost:8000/api/v1/teams/$TEAM/files/$FID/download
```

Archives are **never** extracted server-side. The `check-archive` endpoint
validates Zip Slip / symlink-bomb safety before any client code touches the
contents.

## 7. Chat

```bash
# Send
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{"body":"Drafts due Friday."}' \
  http://localhost:8000/api/v1/teams/$TEAM/messages

# Pull history (most recent first)
curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/messages?limit=50"
```

For real-time, connect a WebSocket:

```text
ws://localhost:8000/api/v1/teams/$TEAM/chat?access=<tl_access cookie value>
```

The server assigns monotonic `seq` numbers. The client may pass
`?before_seq=N` to resync on reconnect.

## 8. Schedules and overload

```bash
# Set a plan (member + leader can edit their own)
curl -sS -b cookies.txt -X PUT \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d '{
    "slots":[{"weekday":1,"start_minute":540,"end_minute":1020,"note":null}],
    "weekly_cap_hours":25
  }' "http://localhost:8000/api/v1/teams/$TEAM/schedules?user_id=$ADA"

# Calendar / timeline / overload
curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/calendar?week_start=2026-01-05"
curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/timeline?start=2026-01-05&end=2026-01-12"
curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/overload?week_start=2026-01-05"
```

The overload endpoint returns a list of `{user_id, week_start, assigned_hours, cap_hours}`
when a member is over their cap.

## 9. Notifications

The scheduler fires reminders at 3 days, 1 day, and on overdue
transitions. In-app notifications are visible at:

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/notifications
curl -sS -b cookies.txt http://localhost:8000/api/v1/notifications/unread-count
curl -sS -b cookies.txt -X POST -H "X-CSRF-Token: $CSRF" \
  http://localhost:8000/api/v1/notifications/read-all
```

## 10. Scoring dashboard

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/projects/$PROJECT/score
# Returns per-participant totals, by-category breakdowns, adjustments,
# and a suggested_order list (descending points, name tie-breaker).
```

Add an adjustment (leader only):

```bash
curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{\"user_id\":\"$ADA\",\"delta\":\"2.5\",\"reason\":\"extra review\"}" \
  http://localhost:8000/api/v1/projects/$PROJECT/adjustments
```

## 11. Finalise the author order

```bash
SNAP=$(curl -sS -b cookies.txt -X POST \
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" \
  -d "{\"positions\":[
    {\"position\":1,\"user_id\":\"$ADA\"},
    {\"position\":2,\"user_id\":\"$BABBAGE\"}
  ]}" \
  http://localhost:8000/api/v1/projects/$PROJECT/author-order/finalize \
  | jq -r .snapshot_id)

# Exports
curl -sS -b cookies.txt -OJ "http://localhost:8000/api/v1/projects/$PROJECT/author-order/export.pdf?snapshot_id=$SNAP"
curl -sS -b cookies.txt    "http://localhost:8000/api/v1/projects/$PROJECT/author-order/export.csv?snapshot_id=$SNAP"
curl -sS -b cookies.txt    "http://localhost:8000/api/v1/projects/$PROJECT/author-order/statement.txt?snapshot_id=$SNAP"
```

The snapshot is **immutable**. A re-finalise creates a new snapshot;
older snapshots remain queryable for audit purposes.

## Troubleshooting

| Symptom                                  | Likely cause / fix                                        |
|------------------------------------------|-----------------------------------------------------------|
| `401 auth.required` on every call        | Cookie jar not reused: re-run `curl -c cookies.txt`.      |
| `403 auth.forbidden`                     | Caller is not the leader / not a member of the team.      |
| `429 rate.exceeded`                      | Back off; login is capped at 10/min/email.                |
| `csrf.required`                          | Add `-H "X-CSRF-Token: $CSRF"` for unsafe verbs.          |
| `team.archived` (423)                    | Unarchive via DB or recreate the team.                    |
| `score.adjustment_add` audit row missing | Check that the caller is the team leader.                 |
