/**
 * Cloudflare Worker entrypoint for TeamLedger — keep-alive cron ping.
 *
 * Replaces the earlier Containers proxy (git history; src/container.ts):
 * Containers need the paid Workers plan, so this Worker now does a single
 * job on the free plan —
 *
 *   scheduled() → GET https://teamledger-1.onrender.com/api/v1/health/db
 *
 * every 5 minutes (see `triggers.crons` in wrangler.jsonc). Render Free
 * spins down after 15 minutes without inbound traffic, so this ping keeps
 * the API warm; the health check's SELECT 1 also keeps Neon's compute
 * warm. fetch() just redirects the workers.dev URL to the production site.
 */

const RENDER_HEALTH_URL = "https://teamledger-1.onrender.com/api/v1/health/db";
const SITE_URL = "https://teamledger-rifat-0046.vercel.app/";

export default {
  async fetch(_request: Request): Promise<Response> {
    return Response.redirect(SITE_URL, 302);
  },

  async scheduled(_event: ScheduledController, _env: Env): Promise<void> {
    await ping();
  },
};

async function ping(): Promise<void> {
  try {
    const res = await fetch(RENDER_HEALTH_URL, {
      headers: { "user-agent": "teamledger-keepalive" },
      signal: AbortSignal.timeout(30_000),
    });
    const body = await res.text();
    console.log(`keep-alive -> ${res.status}: ${body.slice(0, 160)}`);
  } catch (err) {
    // Re-throw so the failed invocation is visible in cron logs/metrics.
    console.error(`keep-alive failed: ${String(err)}`);
    throw err;
  }
}

/** No bindings — the ping target is a hardcoded public URL. */
export interface Env {}
