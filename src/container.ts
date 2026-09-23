/**
 * TeamledgerContainer — Durable Object that owns the FastAPI container.
 *
 * We use a single, named, always-on container instance to serve the entire
 * app. All public requests flow Worker -> DO (via getContainer()) -> container
 * (uvicorn on port 8080).
 *
 * The container's lifecycle is controlled by `defaultPort`, `sleepAfter`,
 * and `envVars` declared on this class. Wrangler reads the image path from
 * `wrangler.jsonc`'s `containers[]` block; this class only describes how
 * the DO proxies requests and starts the container.
 *
 * Secrets (DATABASE_URL, SECRET_KEY, RESEND_API_KEY, RESEND_FROM) are
 * read directly from the bound env via `cloudflare:workers` and injected
 * into the container as environment variables at start time. They are
 * never baked into the Worker source.
 */

import { Container } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

export class TeamledgerContainer extends Container {
  /** Container listens on 8080 (matches backend/Dockerfile EXPOSE). */
  defaultPort = 8080;

  /** Keep the container warm for ~10 minutes after the last request. */
  sleepAfter = "10m";

  /**
   * Environment variables passed to the FastAPI process on every start.
   * Secrets come from Worker Secrets (`wrangler secret put <NAME>`); the
   * `cloudflare:workers` import gives synchronous access to the bound
   * `env` object at module init.
   */
  envVars = {
    // Non-secret defaults
    APP_ENV: "production",
    PORT: "8080",
    MAIL_BACKEND: "resend",
    STORAGE_BACKEND: "local",
    STORAGE_LOCAL_ROOT: "/app/storage/files",
    AVATAR_LOCAL_ROOT: "/app/storage/avatars",

    // Secrets — read from Worker env. Empty string when unset so the
    // FastAPI app can still start; it logs a warning in that case.
    DATABASE_URL: env.DATABASE_URL ?? "",
    SECRET_KEY: env.SECRET_KEY ?? "",
    RESEND_API_KEY: env.RESEND_API_KEY ?? "",
    RESEND_FROM: env.RESEND_FROM ?? "",
    PUBLIC_BASE_URL: env.PUBLIC_BASE_URL ?? "",
    CORS_ALLOWED_ORIGINS: env.CORS_ALLOWED_ORIGINS ?? "",
  };

  override onStart() {
    console.log("[teamledger] container started");
  }

  override onStop() {
    console.log("[teamledger] container stopped");
  }

  override onError(error: unknown) {
    console.log("[teamledger] container error:", error);
  }
}
