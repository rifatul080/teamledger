# Deploying TeamLedger on Cloudflare Containers

Cloudflare Containers is in early access and requires the **Workers Paid
plan** ($5/month minimum + per-instance-hours). It's not part of the free
tier, but it's cheap: $0.012/hr per running instance.

This guide assumes you've already created a Cloudflare account and have
`wrangler` installed. Total time once you have the prerequisites: ~10 minutes.

## Prerequisites

1. **A Cloudflare account** with the Workers Paid plan enabled.
2. **A free Postgres database** — get one from <https://neon.tech>:
   - Sign up, click "Create project", name it `teamledger`.
   - Copy the connection string. It looks like:
     ```
     postgresql://USER:PASS@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
3. **A Resend API key** for outgoing email — get one from
   <https://resend.com/api-keys>. Free tier: 100 emails/day.
4. **A generated SECRET_KEY** — at least 32 random bytes:
   ```bash
   python -c "import secrets;print(secrets.token_urlsafe(48))"
   ```

## Step 1 — Install the wrangler CLI

```bash
npm install -g wrangler
wrangler --version   # should print wrangler 3.x or newer
```

## Step 2 — Log in

```bash
wrangler login
```

A browser tab opens; complete the OAuth dance. You should see
"Successfully logged in" in your terminal.

## Step 3 — Edit the env vars in `wrangler.jsonc`

Open the file at the repo root. Replace the placeholders:

```jsonc
"PUBLIC_BASE_URL": "https://teamledger.<your-subdomain>.workers.dev",
"CORS_ALLOWED_ORIGINS": "https://teamledger.<your-subdomain>.workers.dev",
```

The subdomain is fixed by Cloudflare based on your account. After the
first deploy, Cloudflare prints the exact URL — you can copy it back into
the config and redeploy.

## Step 4 — Push secrets

Wrangler keeps secrets out of git. Run these from the repo root; each
prompts you to paste the value:

```bash
wrangler secret put DATABASE_URL
# paste the Neon connection string, hit Enter

wrangler secret put SECRET_KEY
# paste the random 48-byte string you generated

wrangler secret put RESEND_API_KEY
# paste the Resend key (re_xxx...)
```

## Step 5 — Deploy

From the repo root:

```bash
wrangler deploy
```

Cloudflare will:
1. Build the Dockerfile (`./backend/Dockerfile`, two-stage SPA + API).
2. Push the image to Cloudflare's registry.
3. Start one container instance, expose it on your `*.workers.dev` URL.
4. Run `/healthz` probes; mark the deployment healthy once they pass.

First build takes ~3–5 minutes. Subsequent deploys cache the npm + pip
layers and finish in under a minute.

## Step 6 — Smoke test

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
| CORS error in browser console | Make sure `CORS_ALLOWED_ORIGINS` in `wrangler.jsonc` matches the URL you're visiting |
| Email never arrives | `RESEND_FROM` must be a domain you've verified in Resend, or use the sandbox `onboarding@resend.dev` |

## What you don't need to configure

- **`BUILD_COMMAND`** — none. The Dockerfile handles the SPA build.
- **`START_COMMAND`** — none. The Dockerfile's `CMD` runs migrations then
  uvicorn on `${PORT:-8000}`, and Cloudflare sets `PORT=8080`.
- **A custom domain** — `*.workers.dev` works out of the box.
- **HTTPS** — Cloudflare handles TLS termination in front of the container.

## Updating later

```bash
git pull
wrangler deploy
```

That's it. Cloudflare watches `main` only if you set up a GitHub Actions
workflow; the manual command above is enough for most teams.
