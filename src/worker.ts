/**
 * Cloudflare Worker entrypoint for TeamLedger.
 *
 * Every public request hits this Worker. The Worker delegates each request
 * to a single long-running container that runs the FastAPI app on :8080.
 *
 *   internet -> Workers edge -> this Worker -> Container (uvicorn) -> SPA / API
 *
 * The container is reached via the Durable Object binding named "API"
 * (`wrangler.jsonc` -> durable_objects.bindings[].name == "API"). We use
 * `getContainer` with a stable name to keep a single container instance
 * alive for the entire app rather than spinning one up per request.
 */

import { getContainer } from "@cloudflare/containers";

export { TeamledgerContainer } from "./container";

// The container instance name. Bumping this string on deploy would force
// a fresh container (do not change casually — it loses in-memory state).
const CONTAINER_NAME = "teamledger-api";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Forward the request to the named container instance. The container's
    // uvicorn server preserves the URL path so /api/v1/* and the SPA
    // routes resolve identically on the FastAPI side.
    return getContainer(env.API, CONTAINER_NAME).fetch(request);
  },
};

export interface Env {
  /** Container DO binding — declared in wrangler.jsonc. */
  API: DurableObjectNamespace;

  // Secrets (set with `wrangler secret put <NAME>`):
  DATABASE_URL?: string;
  SECRET_KEY?: string;
  RESEND_API_KEY?: string;
  RESEND_FROM?: string;

  // Non-secret overrides (set with `wrangler secret put` or via vars in
  // wrangler.jsonc):
  PUBLIC_BASE_URL?: string;
  CORS_ALLOWED_ORIGINS?: string;
}
