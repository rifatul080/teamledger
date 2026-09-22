import { useCallback, useEffect, useRef, useState } from "react";

export type Toast = {
  id: number;
  title: string;
  body?: string;
  kind?: "info" | "ok" | "warn" | "error";
  timeout?: number;
};

let _id = 0;
const listeners = new Set<(t: Toast) => void>();

export function pushToast(t: Omit<Toast, "id">) {
  const id = ++_id;
  const toast: Toast = { kind: "info", timeout: 4500, ...t, id };
  listeners.forEach((fn) => fn(toast));
}

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((cur) => cur.filter((t) => t.id !== id));
    const tm = timers.current.get(id);
    if (tm) clearTimeout(tm);
    timers.current.delete(id);
  }, []);

  useEffect(() => {
    const onPush = (t: Toast) => {
      setToasts((cur) => [...cur, t]);
      if (t.timeout && t.timeout > 0) {
        const tm = setTimeout(() => dismiss(t.id), t.timeout);
        timers.current.set(t.id, tm);
      }
    };
    listeners.add(onPush);
    return () => {
      listeners.delete(onPush);
    };
  }, [dismiss]);

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm"
      aria-live="polite"
      role="status"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`card flex items-start gap-2 shadow-md ${
            t.kind === "error"
              ? "border-danger/40"
              : t.kind === "warn"
                ? "border-warn/40"
                : t.kind === "ok"
                  ? "border-ok/40"
                  : ""
          }`}
          role="alert"
        >
          <span
            className={`mt-0.5 inline-block w-2 h-2 rounded-full ${
              t.kind === "error"
                ? "bg-danger"
                : t.kind === "warn"
                  ? "bg-warn"
                  : t.kind === "ok"
                    ? "bg-ok"
                    : "bg-info"
            }`}
            aria-hidden="true"
          />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-ink">{t.title}</div>
            {t.body && <div className="text-meta">{t.body}</div>}
          </div>
          <button
            className="btn-ghost btn-sm"
            aria-label="Dismiss"
            onClick={() => dismiss(t.id)}
          >
            <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M3 3l10 10M13 3L3 13" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
