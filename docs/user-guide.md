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

In the app, open a team and press "Open chat". The page connects to
`wss(s)://<api-origin>/api/v1/teams/$TEAM/chat`, authenticating with the
`tl_access` cookie, and falls back to REST sends plus a 30-second poll
if the socket cannot be established (a Vercel rewrite does not proxy
WebSocket upgrades, so a cross-origin chat needs the socket pointed
straight at the API origin). The status pill in the corner shows which mode
you are in: **Live**, **Reconnecting…**, or **Offline**.

**Mentions.** Type `@` in the composer to autocomplete a teammate; Tab,
Enter, or a click inserts `@Display Name`. The mention is stored with the
message, rendered in the accent colour, and highlighted when it is
yours. On the server, the longest matching display name wins, so
`@Ada Lovelace can you look` resolves to Ada rather than swallowing the
sentence.

```bash
# Send (REST works identically)
curl -sS -b cookies.txt -X POST `
  -H 'Content-Type: application/json' -H "X-CSRF-Token: $CSRF" `
  -d '{"body":"Drafts due Friday @Babbage"}' `
  http://localhost:8000/api/v1/teams/$TEAM/messages

# Pull history (newest first)
curl -sS -b cookies.txt "http://localhost:8000/api/v1/teams/$TEAM/messages?limit=50"
```

The server assigns monotonic `seq` numbers. The client may pass
`?before_seq=N` to resync on reconnect, and `?last_seq=N` to get
everything newer on open.

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

Two sources feed the same inbox.

**Event-based (immediate).** Assigning a task, reassigning one, and
mentioning someone in chat all create a notification row in the same
transaction as the action, and send the recipient an email on a worker
thread. The in-app row is what the sidebar badge and the notification
bar under the header count; the email is what catches the person who is
not looking at the app. Assigning a task to yourself does not notify
you.

**Time-based (scheduled).** Reminders at 3 days, 1 day, and on overdue
transitions, de-duplicated per (kind, task, recipient, bucket) so a
re-run cannot double-send.

In the app, unread items appear as a bar under the header with a one-line
summary and an "Open activity" link; a toast also fires when one arrives
while the tab is in the foreground. `/notifications` shows the full feed
with per-kind tabs and "Mark all read".

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/notifications
curl -sS -b cookies.txt http://localhost:8000/api/v1/notifications/unread-count
curl -sS -b cookies.txt -X POST -H "X-CSRF-Token: $CSRF" `
  http://localhost:8000/api/v1/notifications/read-all
```

Email delivery follows `MAIL_BACKEND`: `console` (dev), `smtp`, or
`resend`. Assignment and mention mail is best-effort — a mail provider
outage never fails the action that triggered it.

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


## v2 walkthrough additions

### Public landing page and signup

Open `https://your-app/` (or `http://localhost:5173/` in dev). The
landing page explains who TeamLedger is for (research teams working on a
paper, thesis, or grant) and offers a "Create your account" button.

Create an account:
- Your email — academic domains (e.g. `cs.ox.ac.uk`) are detected and
  pre-fill the institution field.
- Your display name — shown next to everything you do; can be changed
  later from the Profile page.
- Institution — pre-filled if your email was academic; confirm or edit.
- Timezone — pre-filled from the browser.
- Password — at least 10 chars, including a letter and a digit.

After signup you are auto-logged in. A verification link is sent to your
email (in dev it prints to the backend console); click it or paste the
URL into your browser to confirm. Resend from the Profile page is fine.

### First-team onboarding

Creating your first team is a single form: **team name**, an optional
one-liner of context, and an optional "kind of work" (conference paper,
journal, thesis, lab research, grant). The work type only pre-fills the
contribution categories used later for author order; everything stays
editable in project settings.

Submitting it drops you straight onto the team page with the members panel
open and an invite link already generated, because bringing people in is
the next thing you want to do.

A pure invitee (someone who only joins existing teams and never creates
their own) never sees this wizard — they go straight to the dashboard.

### Creating a second team (condensed)

Same one-line form. If you already belong to a team, the "New team" button
from `/teams` still works; the form just notes that you are already on
one and offers to open it.

### Social sign-in

If the server has Google or Facebook credentials, the sign-in and
sign-up pages show a button per configured provider. It is the same
session as a password login: the callback sets the identical cookie
bundle, so the 14-day refresh cookie behaves the same way.

Server environment (see `backend/.env.example`):

```bash
GOOGLE_CLIENT_ID=...            GOOGLE_CLIENT_SECRET=...
FACEBOOK_CLIENT_ID=...          FACEBOOK_CLIENT_SECRET=...
OAUTH_REDIRECT_BASE=https://your-api-origin
```

Register the exact callback with each provider:
`{OAUTH_REDIRECT_BASE}/api/v1/auth/oauth/google/callback` (same for
`facebook`). Leave a pair blank and that provider simply does not
appear. A social sign-in is matched to an existing account by email and
marks it verified; a new account gets a random, unusable password, so it
can only ever be entered through the provider.

### Command palette

Press `Ctrl+K` (or `Cmd+K` on macOS) anywhere to open the command
palette. Type to fuzzy-search teams, projects, tasks, or people; arrow
keys + Enter to navigate. The palette also exposes quick actions (Go to
dashboard, Go to teams, Create a new team, Toggle light / dark theme,
Show keyboard shortcuts).

Other shortcuts (also documented inside the palette under "?"):
- `Esc` closes the current dialog
- `↑` / `↓` move selection in lists
- `g` then `d` → dashboard
- `g` then `t` → teams
- `g` then `n` → notifications

### Task views

Every project has four task views (Board / List / Calendar / Timeline),
backed by the same data. Switching views does not duplicate, reorder, or
lose anything. Per-project defaults are stored on the project; per-user
overrides (last-used view) are remembered in `localStorage` and override
the project default for you specifically.

### Drag-and-drop on the board

Click and drag a task card between columns to change its status
immediately. The change is sent to the server in the background; if the
server rejects it, you'll see a toast and the card snaps back.

### Profile pictures

Open the Profile page and click "Change photo". Pick an image — the
client crops it to a square, the server re-encodes two sizes
(64 px for lists, 256 px for the profile page), strips the EXIF, and
validates the file by its content, not its extension. A user without a
photo gets a deterministic initials badge on a color derived from their
user ID — the same person always gets the same color.

### Contribution scoring (preview)

The "Scoring" tab on a paper project is where evidence-based author
order comes together. There are four pieces in this build:
- Evidence trail: every point links back to the source task, file, or
  milestone that generated it.
- Author-order simulator: adjust the relative weight per CRediT
  category and watch the author order recompute live. Nothing is
  written to the permanent record until you confirm a weighting.
- Dispute workflow: while the contribution record is still open, any
  member can flag a scored item with a short reason. The leader must
  record a response — adjust the score or explain why it stands —
  before the item can be finalised.
- Finalization: an explicit "Finalize contribution record" action locks
  the scores and author order from silent edits. Subsequent changes
  become a new dated revision rather than an edit-in-place.

The CRediT statement export and anti-gaming flags, plus the
cross-team workload warning shown when assigning a deadline, are wired
into the same project page; details are in `docs/scoring-methodology.md`.

### Activity / notifications

Mentions, thread replies directed at you, and reactions on your messages
share a single activity view at `/notifications`. Filter by kind using
the tabs. "Mark all read" clears everything. Per-team feeds at
`/teams/{id}` also show all activity filtered to that team.

### Public search (command palette)

Press `Ctrl+K` and type any phrase. The palette pulls together matches
across messages, task titles, and file names — all in one box, grouped

### Personal notes

`/notes` is a private scratchpad: title, body, and a pin. Nobody on your
teams can read it — the API filters on the authenticated user, and a note id
belonging to someone else is a 404, not a 403, so it never confirms that an
id exists. Pinned notes sort first.

```bash
curl -sS -b cookies.txt http://localhost:8000/api/v1/me/notes
curl -sS -b cookies.txt -X POST -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Ask about the camera-ready","content":"Email the editor Monday"}' \
  http://localhost:8000/api/v1/me/notes
```

### My week (planner)

`/schedule` is your own availability plus the deadlines assigned to you.
Add time blocks per weekday, set a weekly cap, and save; the page then shows
your tasks and milestones for that week and warns you when your booked hours
exceed the cap.

Leaders can also write a plan for any member. A member can only write their
own — editing somebody else's availability is a 403.

```bash
curl -sS -b cookies.txt -X PUT -H "X-CSRF-Token: $CSRF" \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$ADA\",\"weekly_cap_hours\":25,
       \"slots\":[{\"weekday\":0,\"start_minute\":540,\"end_minute\":1020}]}" \
  http://localhost:8000/api/v1/teams/$TEAM/schedules

curl -sS -b cookies.txt \
  "http://localhost:8000/api/v1/teams/$TEAM/calendar?start=2026-01-05&end=2026-01-11&user_id=$ADA"
```

### Assigning work in the UI

On a project page: **New goal**, **Add milestone**, and **Assign task** — the
task form takes a milestone, a teammate from the project's participant list,
a contribution category, an estimate, and a required due date. On a goal
page, each milestone lists its tasks with the assignee and deadline and
offers the same assignment inline. Assigning a task is what sends the
notification and the email.

by type.