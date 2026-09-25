# Deploy: Vercel (frontend) + Render (backend)

This is the split-deploy layout. Use it when you want the React SPA on
Vercel's CDN and the FastAPI backend on Render. Cookies are cross-origin
so the API must set `SameSite=None; Secure`.

## One-time setup

1. **Vercel project**
   - Import this repo.
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Framework Preset**: Vite (auto-detected)
   - **Environment Variables**:
     - `VITE_API_BASE_URL` = `https://<your-render-app>.onrender.com`
       *(no trailing slash, no `/api/v1`)*

2. **Render Web Service** (Docker)
   - Connect this repo as a "Web Service".
   - **Language**: Docker
   - **Dockerfile Path**: `./Dockerfile` *(Render uses the repo root as the build context, so the root Dockerfile works as-is. The root Dockerfile also builds the SPA stage, which is harmless but wasted work for this split deploy — the SPA is served from Vercel.)*
   - **Health Check Path**: `/healthz`
   - **Environment Variables**:
     | Key | Value |
     | --- | ----- |
     | `DATABASE_URL` | `postgresql://<user>:<pwd>@<host>/<db>` (Neon/Supabase/Render Postgres) |
     | `SECRET_KEY` | 32+ random bytes (`openssl rand -hex 32`) |
     | `APP_ENV` | `production` |
     | `MAIL_BACKEND` | `resend` (or `console` while testing) |
     | `RESEND_API_KEY` | *(leave blank if MAIL_BACKEND=console)* |
     | `RESEND_FROM` | `TeamLedger <noreply@your-domain>` |
     | `PUBLIC_BASE_URL` | `https://<your-render-app>.onrender.com` |
     | `CORS_ALLOWED_ORIGINS` | `https://<your-vercel-app>.vercel.app` |
     | `COOKIE_SAMESITE` | `none` *(required for Vercel → Render cross-origin cookies)* |
     | `DEFAULT_TIMEZONE` | `UTC` |

## How it works

- The frontend builds with `VITE_API_BASE_URL` baked in, so every API
  call hits the Render backend directly.
- `credentials: "include"` is set on all fetches so the browser sends
  cookies cross-origin.
- The backend responds with `Access-Control-Allow-Origin` matching the
  Vercel origin and `Access-Control-Allow-Credentials: true` (already
  wired by FastAPI's `CORSMiddleware`).
- Cookies are set with `SameSite=None; Secure` because `COOKIE_SAMESITE=none`.
  `Secure` forces HTTPS — Render's free tier already gives you HTTPS.

## Local dev (unchanged)

- `cd backend && uvicorn app.main:app --reload` (port 8000)
- `cd frontend && npm run dev` (port 5173)
- Leave `VITE_API_BASE_URL` empty. Vite proxies `/api` to `127.0.0.1:8000`.

## Troubleshooting

- **Build error `failed to calculate checksum ... "/backend/app/__init__.py": not found`** on Render: this is almost always a **stale BuildKit cache**, not a real path issue. The root `Dockerfile` has the correct `COPY backend/app/...` paths. Two ways to fix:
  1. **Easiest**: in the Render Dashboard, go to your service → Settings → **"Clear build cache"** → trigger a new deploy.
  2. **Or**: open Settings → **Docker Command** and add `docker build --no-cache` (Render will pass this through).
  3. **Or**: edit any tracked file and push a commit — Render's cache is keyed on commit SHA, so a fresh commit forces a fresh build.
- **Render Dashboard fields not matching `render.yaml`**: if your Render service was created **via Dashboard** (not as a Blueprint), it does NOT read `dockerfilePath` from `render.yaml`. You must manually set **Dockerfile Path** to `./Dockerfile` in the service's Settings page. To make `render.yaml` authoritative, delete the service and re-create it as a Blueprint (New → Blueprint).
- **Cookies not sticking on Vercel**: confirm `COOKIE_SAMESITE=none` and
  that you're hitting the page over `https://`. `SameSite=None` requires
  `Secure`, which requires HTTPS.
- **CORS error in browser**: make sure `CORS_ALLOWED_ORIGINS` exactly
  matches the Vercel origin (no trailing slash, scheme included).
- **502 from Render**: check that the `DATABASE_URL` is reachable from
  Render's network and that `alembic upgrade head` ran (visible in the
  Render deploy log).

## Switching back to mono-host

If you want to host everything on Render (no Vercel), revert
`render.yaml`'s `dockerfilePath` to `./Dockerfile` and remove the
`VITE_API_BASE_URL` env var on Vercel (or just delete the Vercel project).
The same Render service will then build the SPA inside the Docker image
and serve it at `/`.
