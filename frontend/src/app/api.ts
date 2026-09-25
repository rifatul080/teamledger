// Thin fetch wrapper. Same-origin + credentials so HttpOnly cookies flow.
// Reads X-CSRF-Token from cookie for unsafe methods.
//
// API base URL is read from VITE_API_BASE_URL when set (cross-origin
// deploy: Vercel frontend + Render/Fly backend). When unset (local dev or
// same-origin mono-host deploy), requests go to "<origin>/api/v1/...".

const BASE_PATH = "/api/v1";

function getBaseUrl(): string {
  // Vite injects import.meta.env at build time. Anything starting with
  // https:// or http:// is treated as an absolute origin; anything else is
  // appended to the current origin (default same-origin).
  const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
  if (!raw) return window.location.origin;
  if (/^https?:\/\//i.test(raw)) return raw.replace(/\/+$/, "");
  // Same-origin-relative override (e.g. "/api").
  return new URL(raw, window.location.origin).origin;
}

const BASE = getBaseUrl();

export function buildUrl(path: string, params?: ApiOpts["params"]): URL {
  // BASE is an origin (e.g. "https://api.example.com" or window.location.origin).
  // path is what callers pass — "/foo", "/auth/login", etc. We prepend
  // BASE_PATH ("/api/v1") so requests hit the versioned API namespace.
  // Both BASE_PATH and path are normalized to start with a single "/".
  const normalizedPath =
    (BASE_PATH.endsWith("/") ? BASE_PATH : BASE_PATH + "/") +
    (path.startsWith("/") ? path.slice(1) : path);
  const url = new URL(BASE.replace(/\/+$/, "") + normalizedPath);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

const CSRF_COOKIE = "tl_csrf";

function getCsrf(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.split(/;\s*/).find((c) => c.startsWith(`${CSRF_COOKIE}=`));
  if (!m) return null;
  try {
    return decodeURIComponent(m.slice(CSRF_COOKIE.length + 1));
  } catch {
    return null;
  }
}

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export type ApiOpts = {
  method?: Method;
  json?: unknown;
  body?: BodyInit;
  params?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  /** When true, do not set Content-Type (use for FormData). */
  raw?: boolean;
  /** Skip CSRF — for first-time login/signup before a cookie is present. */
  skipCsrf?: boolean;
};

export async function api<T = unknown>(path: string, opts: ApiOpts = {}): Promise<T> {
  const url = buildUrl(path, opts.params);
  const headers: Record<string, string> = {};
  if (!opts.raw) headers["Content-Type"] = "application/json";
  const method = opts.method ?? "GET";
  if (method !== "GET" && !opts.skipCsrf) {
    const csrf = getCsrf();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  const init: RequestInit = {
    method,
    credentials: "include",
    headers,
  };
  if (opts.signal) init.signal = opts.signal;
  if (opts.body !== undefined) init.body = opts.body;
  else if (opts.json !== undefined) init.body = JSON.stringify(opts.json);

  const res = await fetch(url.toString(), init);
  const ct = res.headers.get("content-type") ?? "";
  let payload: unknown = undefined;
  if (ct.includes("application/json")) {
    try {
      payload = await res.json();
    } catch {
      payload = undefined;
    }
  } else if (res.status !== 204) {
    try {
      payload = await res.text();
    } catch {
      /* ignore */
    }
  }
  if (!res.ok) {
    const body = (payload ?? {}) as { code?: string; message?: string; details?: unknown };
    throw new ApiError(
      res.status,
      body.code ?? `http.${res.status}`,
      body.message ?? res.statusText,
      body.details,
    );
  }
  return payload as T;
}

export async function apiDownload(path: string, opts: ApiOpts = {}): Promise<Blob> {
  const url = buildUrl(path, opts.params);
  const headers: Record<string, string> = {};
  const method = opts.method ?? "GET";
  if (method !== "GET" && !opts.skipCsrf) {
    const csrf = getCsrf();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  const res = await fetch(url.toString(), {
    method,
    credentials: "include",
    headers,
    body:
      opts.body ?? (opts.json !== undefined ? JSON.stringify(opts.json) : undefined),
  });
  if (!res.ok) throw new ApiError(res.status, `http.${res.status}`, res.statusText);
  return res.blob();
}
