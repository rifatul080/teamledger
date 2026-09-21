// Thin fetch wrapper. Same-origin + credentials so HttpOnly cookies flow.
// Reads X-CSRF-Token from /csrf endpoint or from cookie for unsafe methods.

const BASE = "/api/v1";

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

const CSRF_COOKIE = "tl_csrf";

function getCsrf(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.split(/;\s*/).find((c) => c.startsWith(`${CSRF_COOKIE}=`));
  if (!m) return null;
  return decodeURIComponent(m.slice(CSRF_COOKIE.length + 1));
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  constructor(status: number, body: { code?: string; message?: string; details?: unknown }) {
    super(body.message ?? `HTTP ${status}`);
    this.status = status;
    this.code = body.code ?? "unknown";
    this.details = body.details;
  }
}

export async function api<T = unknown>(
  path: string,
  init: { method?: Method; json?: unknown; body?: BodyInit; params?: Record<string, string | number | boolean>; signal?: AbortSignal } = {},
): Promise<T> {
  const method = init.method ?? "GET";
  const search = init.params
    ? "?" + new URLSearchParams(Object.entries(init.params).map(([k, v]) => [k, String(v)])).toString()
    : "";
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined = init.body;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  if (method !== "GET") {
    const csrf = getCsrf();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  const res = await fetch(BASE + path + search, {
    method,
    headers,
    body,
    credentials: "include",
    signal: init.signal,
  });
  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }
  if (!res.ok) {
    const errBody = (parsed && typeof parsed === "object" ? parsed : {}) as {
      code?: string;
      message?: string;
      details?: unknown;
    };
    throw new ApiError(res.status, errBody);
  }
  return parsed as T;
}

export async function apiUpload<T = unknown>(path: string, form: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const csrf = getCsrf();
  if (csrf) headers["X-CSRF-Token"] = csrf;
  const res = await fetch(BASE + path, {
    method: "POST",
    body: form,
    credentials: "include",
    headers,
  });
  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }
  if (!res.ok) {
    const errBody = (parsed && typeof parsed === "object" ? parsed : {}) as {
      code?: string;
      message?: string;
    };
    throw new ApiError(res.status, errBody);
  }
  return parsed as T;
}

export function downloadUrl(path: string, params: Record<string, string> = {}): string {
  const search = new URLSearchParams(params).toString();
  return BASE + path + (search ? `?${search}` : "");
}

export async function openDownload(path: string, params: Record<string, string> = {}): Promise<void> {
  const url = downloadUrl(path, params);
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok) {
    let body: { code?: string; message?: string } = {};
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    throw new ApiError(res.status, body);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  const cd = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(cd);
  a.download = match && match[1] ? match[1] : "download";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}
