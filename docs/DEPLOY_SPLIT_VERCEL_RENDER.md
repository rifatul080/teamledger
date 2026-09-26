# Deploy: Vercel (frontend) + Render (backend)

Split-deploy layout: React SPA on Vercel's CDN, FastAPI on Render, one
Postgres (Neon). Visitors only ever talk to the Vercel origin — Vercel
rewrites `/api/*` to Render. That keeps cookies first-party and keeps the
CSRF double-submit check working.

```
browser ──► https://<project>-<scope>.vercel.app ──rewrite /api/*──► https://<service>.onrender.com
              (static SPA, first-party cookies)                       (FastAPI + Postgres)
```

> The Docker image still builds the SPA, so `https://<service>.onrender.com`
> keeps working as a same-origin fallback. Handy for debugging.

## Why a rewrite instead of calling Render directly

The API authenticates with cookies and protects unsafe methods with a
double-submit CSRF token: `app/api/deps.py::require_csrf` compares the
`tl_csrf` cookie against the `X-CSRF-Token` header, and
`frontend/src/app/api.ts::getCsrf()` reads that cookie from
`document.cookie`.

Cookies are host-only. JS running on the Vercel origin **cannot read a
cookie set by the Render origin**, so with direct cross-origin calls every
POST/PATCH/DELETE from a signed-in user fails with `403 auth.csrf`. The
rewrite deletes the whole problem class: one origin, no preflight, no
third-party cookies.

## 1. Vercel project

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Framework Preset | Vite (auto-detected) |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Install Command | `npm ci` |

Environment variables: **leave `VITE_API_BASE_URL` unset (or empty).** The
SPA then resolves the API against its own origin (`getBaseUrl()` in
`src/app/api.ts`) and the rewrite below forwards `/api/*` to Render.
Setting it to the Render URL switches the app into direct cross-origin
mode, which breaks CSRF — see the alternative at the bottom.

`frontend/vercel.json` holds the rewrite; `/api/:path*` must come **before**
the SPA catch-all:

```json
"rewrites": [
  { "source": "/api/:path*", "destination": "https://<service>.onrender.com/api/:path*" },
  { "source": "/(.*)", "destination": "/index.html" }
]
```

### Turn off Deployment Protection

A preview URL such as `https://<project>-<hash>-<scope>.vercel.app` is
gated by Vercel Authentication and returns Vercel's **login page with HTTP
200**, which is easy to mistake for a working deploy. Either:

* use the production domain (`https://<project>-<scope>.vercel.app` or a
  custom domain), or
* disable the gate: **Project → Settings → Deployment Protection → Vercel
  Authentication → Disabled** (or scope it to *Standard Protection* so
  production stays public).

## 2. Render service

New **Web Service** from this repo: Runtime **Docker**, Dockerfile Path
`./Dockerfile` (Render always uses the repo root as the build context).

| Env var | Value | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://…` (Neon) | required secret |
| `SECRET_KEY` | 32+ random bytes | required secret |
| `APP_ENV` | `production` | hardens cookies |
| `PUBLIC_BASE_URL` | `https://<project>-<scope>.vercel.app` | **SPA origin** — verify/reset/invite links point here |
| `CORS_ALLOWED_ORIGINS` | same Vercel origin | only used if the browser calls Render directly |
| `COOKIE_SAMESITE` | `lax` | correct for same-origin traffic through the rewrite |
| `MAIL_BACKEND` | `resend` (or `console`) | |
| `RESEND_API_KEY` | | blank while `MAIL_BACKEND=console` |
| `RESEND_FROM` | `TeamLedger <noreply@…>` | |
| `DEFAULT_TIMEZONE` | `UTC` | |

Health Check Path: `/healthz`.

`render.yaml` at the repo root is the intended shape of this service. If
the service was created by hand in the Dashboard (it will be named
`teamledger-1`, not `teamledger-api`), Render ignores that file — copy the
values above in by hand.

## 3. Never shuts down

Two independent platform timers can put the app to sleep. Neither is an
app bug.

| Layer | Free behaviour | Fix |
| --- | --- | --- |
| Render web service | **Spins down after 15 minutes without inbound traffic.** Waking takes **about one minute**, and Render shows a loading page to the connecting browser meanwhile. Free instances also lose their local filesystem on every spin-down / redeploy / restart, and cannot attach a persistent disk. | Give the service a paid compute plan: `0.5c-512mb` (legacy name *Starter*, 0.5 CPU / 512 MB). Any paid plan removes the spin-down limitation. Dashboard → service → Settings → **Compute plan** (labelled *Instance Type* in older dashboards). |
| Neon Postgres | **Compute scales to zero after 5 minutes of inactivity** — fixed on the Free plan; paid plans can disable it. | Resume takes only **a few hundred milliseconds**, so it is usually harmless. Keep it warm by pinging a DB-touching endpoint; `/api/v1/health/db` exists for exactly this. |

Keep-alive pings cannot fully replace the paid plan. UptimeRobot's free
interval is 5 minutes, and one missed sample still puts a visitor on the
1-minute cold-start path (that is what produced the "down for 0h 6m 25s"
alert: a 5-minute sampling interval reports a single failed sample as
~5 minutes of downtime). If "never shuts down" is a hard requirement,
upgrade the Render service — Render's own free-tier page says *"Do not use
them for production applications."*

Recommended monitors (all unauthenticated and cheap):

| URL | Purpose |
| --- | --- |
| `https://<service>.onrender.com/healthz` | Render's own health check — liveness |
| `https://<service>.onrender.com/api/v1/health` | liveness, versioned API |
| `https://<service>.onrender.com/api/v1/health/db` | readiness — `SELECT 1` + applied migration revision; also keeps Neon awake |

Point probes at the **Render** host, not the Vercel one: with the rewrite
in place a probe against Vercel only proves Vercel is up.

Optional: uploads (avatars, team files) live on the container's ephemeral
disk (`STORAGE_LOCAL_ROOT=./storage/files`) and vanish on restart. A paid
plan can attach a persistent disk mounted at `/app/storage`; note that a
disk disables zero-downtime deploys.

## 4. Verify the connection

```bash
# Backend directly
curl -sS https://<service>.onrender.com/healthz
curl -sS https://<service>.onrender.com/api/v1/health
curl -sS https://<service>.onrender.com/api/v1/health/db

# Through the Vercel rewrite — must return the same JSON, not index.html
curl -sS https://<project>-<scope>.vercel.app/api/v1/health
```

Then sign in **through the Vercel URL** and create something (a team or a
project). That exercises POST + the CSRF check end to end.

## Local dev (unchanged)

* `cd backend && uvicorn app.main:app --reload` (port 8000)
* `cd frontend && npm run dev` (port 5173, proxies `/api` to 127.0.0.1:8000)
* Leave `VITE_API_BASE_URL` empty.

## Alternative: direct cross-origin calls

Only do this if the browser must reach Render directly — for example to
use the WebSocket chat endpoint, which a Vercel rewrite cannot proxy. It
costs you three things:

1. `VITE_API_BASE_URL=https://<service>.onrender.com` in Vercel, and drop
   the `/api/:path*` rewrite.
2. On Render: `CORS_ALLOWED_ORIGINS=https://<project>-<scope>.vercel.app`
   and `COOKIE_SAMESITE=none` (`Secure` follows automatically). Preflight
   from an unlisted origin is rejected with **HTTP 400**, not a silent
   failure.
3. Browsers that block third-party cookies (Safari, Firefox ETP, Brave)
   will drop the auth cookies. On top of that the CSRF header cannot be
   built from `document.cookie` cross-origin, so mutations fail with
   `403 auth.csrf` until the token is also exposed some other way — e.g.
   return it in a response header on login/refresh and add that header to
   `expose_headers` in `app/main.py`, then store it client-side.

## Troubleshooting

* **Vercel shows a login page** — Deployment Protection; use the
  production domain or disable it (§1).
* **`/api/v1/health` through Vercel returns `index.html`** — the `/api`
  rewrite is missing, or it is ordered after the SPA catch-all.
* **`403 auth.csrf` after signing in** — direct cross-origin mode with a
  cross-origin cookie; switch to the rewrite.
* **CORS error in the browser console** — direct mode with a mismatched
  origin (must match scheme + host exactly, no trailing slash).
* **Build fails with `failed to calculate checksum ... "/backend/app/__init__.py": not found`** — stale BuildKit cache: Dashboard →
  Settings → **Clear build cache**, then redeploy.
* **502 from Render** — read the deploy log. `alembic upgrade head` runs on
  every boot, so `DATABASE_URL` must be reachable from Render's network.
* **Everyone gets signup-throttled** — rate limiting keys on
  `request.client.host`, which is the proxy's address when requests are
  forwarded, so all visitors share one bucket. Trust the proxy header
  (`FORWARDED_ALLOW_IPS`) before relying on per-IP limits in production.

## Switching back to mono-host

Delete the Vercel project and the `/api/:path*` rewrite: the same Render
service already serves the built SPA at `/` ("The Docker image still
builds the SPA" above), so `https://<service>.onrender.com/dashboard`
works with no further changes.

