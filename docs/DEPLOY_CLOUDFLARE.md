# Deploying TeamLedger on Cloudflare Containers

Cloudflare Containers is in early access and requires the **Workers Paid
plan** ($5/month minimum + per-instance-hours). It's not part of the free
tier, but it's cheap: $0.012/hr per running instance.

## Architecture

Your app runs as a **Container** (the FastAPI + SPA bundle) reachable
only through a **Worker** that proxies every request. The Worker itself
is what Cloudflare exposes on `*.workers.dev`; the container is hidden
behind a Durable Object binding.

```
internet
  │
  ▼
Cloudflare edge ─► Worker (src/worker.ts)
                       │  getContainer(env.API, "teamledger-api")
                       ▼
                  Durable Object  ─►  Container (uvicorn on :8080)
```

Why this shape: Cloudflare Containers only accept traffic from Workers,
not directly from the public Internet. The Worker is the entrypoint.

## Prerequisites

1. **A Cloudflare account** with the **Workers Paid plan** enabled.
2. **Docker** running locally — Wrangler calls `docker build` to produce
   the container image, then pushes it to Cloudflare's registry. Install
   from <https://docs.docker.com/desktop/>.
3. **Node.js 20+** — for running `wrangler` and `npm install` in the
   repo root (to fetch `@cloudflare/containers` and TypeScript types).
4. **A free Postgres database** — get one from <https://neon.tech>:
   - Sign up, click "Create project", name it `teamledger`.
   - Copy the connection string. It looks like:
     ```
     postgresql://USER:PASS@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
5. **A Resend API key** for outgoing email — get one from
   <https://resend.com/api-keys>. Free tier: 100 emails/day.
6. **A generated SECRET_KEY** — at least 32 random bytes:
   ```bash
   python -c "import secrets;print(secrets.token_urlsafe(48))"
   ```

## Step 1 — Install dependencies and log in

From the repo root:

```bash
npm install                # installs wrangler, @cloudflare/containers,
                            # @cloudflare/workers-types, typescript
npx wrangler login          # OAuth browser flow
```

## Step 2 — Push secrets

Each prompts you to paste the value:

```bash
npx wrangler secret put DATABASE_URL      # Neon connection string
npx wrangler secret put SECRET_KEY        # 48-byte random string
npx wrangler secret put RESEND_API_KEY    # Resend key (re_xxx...)
npx wrangler secret put RESEND_FROM       # e.g. "TeamLedger <noreply@teamledger.app>"
```

## Step 3 — (Optional) Update PUBLIC_BASE_URL

After the first deploy, Cloudflare prints the URL your Worker lives at.
It looks like `https://teamledger.<your-subdomain>.workers.dev`. Set it as
a secret so the FastAPI app knows its public origin:

```bash
npx wrangler secret put PUBLIC_BASE_URL        # the URL above
npx wrangler secret put CORS_ALLOWED_ORIGINS   # same URL
```

You can skip this step and the app will fall back to a placeholder; some
emails (verification links) may show the placeholder instead of the real
URL until you fix it.

## Step 4 — Deploy

From the repo root:

```bash
npx wrangler deploy
```

Cloudflare will:
1. Bundle `src/worker.ts` and `src/container.ts` into the Worker.
2. Build the Dockerfile (`./backend/Dockerfile`, two-stage SPA + API).
3. Push the image to Cloudflare's registry.
4. Create the `TeamledgerContainer` Durable Object class.
5. Start one container instance on first request, expose the Worker on
   your `*.workers.dev` URL.
6. Probe the container's port 8080; mark the deployment healthy once
   probes succeed.

First build takes ~3–5 minutes. Subsequent deploys cache the npm + pip
layers and finish in under a minute.

> Wait a few minutes after first deploy before expecting traffic. The
> Worker URL may respond while Cloudflare is still provisioning the
> container; calls into the container can 502 during that window.

## Step 5 — Smoke test

Once deployed, run from your terminal:

```bash
curl https://teamledger.<your-subdomain>.workers.dev/healthz
# expect: {"status":"ok"}

# Browse the app:
start https://teamledger.<your-subdomain>.workers.dev
```

Sign up with a real email; the verification mail goes through Resend.

## Common pitfalls

| Symptom | Fix |
|---|---|
| `Database connection failed` on boot | `wrangler secret put DATABASE_URL` — paste the full Neon URL with `?sslmode=require` |
| `SECRET_KEY must be set in production` | `wrangler secret put SECRET_KEY` — value must be ≥ 32 chars |
| 500 on avatar upload | `libmagic1` is already in the Dockerfile; rebuild with `wrangler deploy` to refresh layers |
| CORS error in browser console | Make sure `CORS_ALLOWED_ORIGINS` matches the URL you're visiting |
| Email never arrives | `RESEND_FROM` must be a domain you've verified in Resend, or use the sandbox `onboarding@resend.dev` |
| `Unexpected fields found in containers field: "port","health","env"` | You're using an old `wrangler.jsonc`. The current schema puts `defaultPort` in the Container class, not in the config. Pull the latest. |
| `Missing entry-point to Worker script or to assets directory` | The config is missing `main`. The current config has `"main": "src/worker.ts"`. Pull the latest. |
| `failed to calculate checksum of ref ... /backend/alembic: not found` | Wrangler defaults the Docker build context to the directory containing `image` (here `./backend/`). The Dockerfile uses repo-root-relative paths (`COPY frontend ./`, `COPY backend/app ./app`), so set `"image_build_context": "./"` (repo root) inside the `containers[]` entry. |
| Container won't start: `Cannot connect to the Docker daemon` | Start Docker Desktop, then re-run `wrangler deploy`. |

## What you don't need to configure

- **`BUILD_COMMAND`** — none. Wrangler handles Worker bundling and calls
  `docker build` for the image; the Dockerfile handles the SPA build.
- **`START_COMMAND`** — none. The Dockerfile's `CMD` runs migrations then
  uvicorn on `${PORT:-8000}`. Cloudflare sets `PORT=8080` for the
  container, which is also the `defaultPort` on `TeamledgerContainer`.
- **A custom domain** — `*.workers.dev` works out of the box.
- **HTTPS** — Cloudflare handles TLS termination in front of the Worker.

## Updating later

```bash
git pull
npx wrangler deploy
```

That's it. The manual command above is enough for most teams; if you want
CI/CD, set up a GitHub Actions workflow that runs `wrangler deploy` on
push to `main` with `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`
secrets in the repo.
