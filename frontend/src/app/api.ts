// Thin fetch wrapper. Same-origin + credentials so HttpOnly cookies flow.
// Reads X-CSRF-Token from cookie for unsafe methods.

const BASE = "/api/v1";

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
  const url = new URL(BASE + path, window.location.origin);
  if (opts.params) {
    for (const [k, v] of Object.entries(opts.params)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
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
  const url = new URL(BASE + path, window.location.origin);
  if (opts.params) {
    for (const [k, v] of Object.entries(opts.params)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
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
