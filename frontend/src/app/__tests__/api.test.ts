// Smoke tests for the api client.
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { ApiError, api, openDownload } from "../api";

const ok = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "tl_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

describe("api", () => {
  it("sends cookies and CSRF header on POST", async () => {
    document.cookie = "tl_csrf=abc123";
    const fetchMock = vi.fn().mockResolvedValue(ok({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api<{ ok: boolean }>("/foo", { method: "POST", json: { a: 1 } });
    expect(result.ok).toBe(true);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/foo");
    expect(init.credentials).toBe("include");
    expect(init.headers["X-CSRF-Token"]).toBe("abc123");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ a: 1 }));
  });

  it("does not attach CSRF on GET", async () => {
    document.cookie = "tl_csrf=abc123";
    const fetchMock = vi.fn().mockResolvedValue(ok({}));
    vi.stubGlobal("fetch", fetchMock);
    await api("/foo");
    const [, init] = fetchMock.mock.calls[0]!;
    expect(init.headers["X-CSRF-Token"]).toBeUndefined();
  });

  it("appends params as a query string", async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok({}));
    vi.stubGlobal("fetch", fetchMock);
    await api("/foo", { params: { a: "1", b: "two" } });
    const [url] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/foo?a=1&b=two");
  });

  it("raises ApiError with status + code on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: "x.fail", message: "bad" }), {
          status: 422,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(api("/foo")).rejects.toMatchObject({
      status: 422,
      code: "x.fail",
      message: "bad",
    } as ApiError);
  });
});

describe("openDownload", () => {
  beforeEach(() => {
    if (!URL.createObjectURL) {
      URL.createObjectURL = () => "blob:fake";
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = () => undefined;
    }
  });
  it("clicks an anchor with the server-provided filename", async () => {
    const headers = new Headers();
    headers.set("Content-Disposition", 'attachment; filename="report.pdf"');
    const blob = new Blob(["hello"], { type: "application/pdf" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(blob, { headers })));

    const created: HTMLAnchorElement[] = [];
    const origCreate = document.createElement.bind(document);
    document.createElement = ((tag: string) => {
      const el = origCreate(tag) as HTMLElement;
      if (tag === "a") {
        created.push(el as HTMLAnchorElement);
        const anchor = el as HTMLAnchorElement;
        anchor.click = vi.fn();
      }
      return el;
    }) as typeof document.createElement;

    await openDownload("/export", { snapshot_id: "abc" });

    expect(created).toHaveLength(1);
    expect(created[0]!.download).toBe("report.pdf");
    expect(created[0]!.click).toHaveBeenCalled();
  });
});
