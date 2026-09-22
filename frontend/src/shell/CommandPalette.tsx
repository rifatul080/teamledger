import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe } from "../app/auth";
import { api } from "../app/api";
import { useTeams } from "../app/data";

export type PaletteHandle = {
  open: () => void;
  close: () => void;
};

export function usePalette() {
  const ref = useRef<PaletteHandle | null>(null);
  return {
    open: () => ref.current?.open(),
    close: () => ref.current?.close(),
    handleRef: ref,
  };
}

type Hit =
  | { kind: "team"; id: string; title: string; sub: string; href: string }
  | { kind: "project"; id: string; title: string; sub: string; href: string }
  | { kind: "task"; id: string; title: string; sub: string; href: string }
  | { kind: "person"; id: string; title: string; sub: string; href: string }
  | { kind: "action"; id: string; title: string; sub: string; run: () => void };

/**
 * Tiny fuzzy matcher: case-insensitive subsequence, scored by tightness.
 * Empty query => empty results list (the input also has "Show shortcuts" entry).
 */
function fuzzy(needle: string, hay: string): number | null {
  if (!needle) return 0;
  needle = needle.toLowerCase();
  hay = hay.toLowerCase();
  const idx = hay.indexOf(needle);
  if (idx === 0) return 1;
  if (idx > 0) return 100 - idx;
  // Subsequence.
  let pos = 0,
    score = 0;
  for (const ch of needle) {
    const found = hay.indexOf(ch, pos);
    if (found === -1) return null;
    score += found - pos;
    pos = found + 1;
  }
  return 200 + score;
}

const ACTIONS: Hit[] = [
  {
    kind: "action",
    id: "go-dashboard",
    title: "Go to dashboard",
    sub: "Open the home dashboard",
    run: () => window.dispatchEvent(new CustomEvent("tl:nav", { detail: "/dashboard" })),
  },
  {
    kind: "action",
    id: "go-teams",
    title: "Go to teams",
    sub: "List all your teams",
    run: () => window.dispatchEvent(new CustomEvent("tl:nav", { detail: "/teams" })),
  },
  {
    kind: "action",
    id: "new-team",
    title: "Create a new team",
    sub: "Start the onboarding wizard",
    run: () => window.dispatchEvent(new CustomEvent("tl:nav", { detail: "/onboarding" })),
  },
  {
    kind: "action",
    id: "notifications",
    title: "Open activity / notifications",
    sub: "Mentions, replies, reactions",
    run: () => window.dispatchEvent(new CustomEvent("tl:nav", { detail: "/notifications" })),
  },
  {
    kind: "action",
    id: "theme",
    title: "Toggle light / dark theme",
    sub: "Switch the app appearance",
    run: () => window.dispatchEvent(new CustomEvent("tl:theme-toggle")),
  },
  {
    kind: "action",
    id: "shortcuts",
    title: "Show keyboard shortcuts",
    sub: "All keys available in the app",
    run: () => window.dispatchEvent(new CustomEvent("tl:show-shortcuts")),
  },
];

const SHORTCUTS: { keys: string; label: string }[] = [
  { keys: "Ctrl/⌘ K", label: "Open command palette" },
  { keys: "Esc", label: "Close the current dialog" },
  { keys: "↑ ↓", label: "Move selection in palette / list" },
  { keys: "Enter", label: "Run the highlighted palette item" },
  { keys: "G then D", label: "Go to dashboard" },
  { keys: "G then T", label: "Go to teams" },
  { keys: "N", label: "New task (when on a milestone page)" },
  { keys: "C", label: "Compose a new chat message" },
  { keys: "/", label: "Focus the search input on the current screen" },
];

export function CommandPalette({ palette }: { palette: ReturnType<typeof usePalette> }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const me = useMe();
  const teams = useTeams();
  const nav = useNavigate();

  // Build fuzzy index across teams, projects, tasks, people.
  const [hits, setHits] = useState<Hit[]>([]);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    (palette.handleRef as React.MutableRefObject<PaletteHandle | null>).current = {
      open: () => {
        setOpen(true);
        setShowShortcuts(false);
        setQ("");
        setActive(0);
      },
      close: () => {
        setOpen(false);
      },
    };
  }, [palette.handleRef]);

  useEffect(() => {
    if (!open || q.trim().length === 0) {
      setHits([]);
      setLoading(false);
      return;
    }
    const term = q.trim();
    setLoading(true);
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;
    (async () => {
      try {
        const out: Hit[] = [];
        // Teams already known.
        for (const t of teams.data ?? []) {
          const score = fuzzy(term, t.name);
          if (score !== null) {
            out.push({
              kind: "team",
              id: t.id,
              title: t.name,
              sub: "Team",
              href: `/teams/${t.id}`,
            });
          }
        }
        // Search API: messages, tasks, files.
        try {
          const res = await api<{
            tasks: { id: string; title: string; project_id: string; status: string }[];
            messages: { id: string; body: string; team_id: string }[];
            files: { id: string; name: string; team_id: string }[];
          }>(`/search?q=${encodeURIComponent(term)}`, { signal: ctl.signal });
          for (const t of res.tasks) {
            out.push({
              kind: "task",
              id: t.id,
              title: t.title,
              sub: `Task · ${t.status}`,
              href: `/projects/${t.project_id}?task=${t.id}`,
            });
          }
          for (const m of res.messages) {
            out.push({
              kind: "team",
              id: m.id,
              title: m.body.slice(0, 60),
              sub: "Message",
              href: `/teams/${m.team_id}/chat?msg=${m.id}`,
            });
          }
          for (const f of res.files) {
            out.push({
              kind: "team",
              id: f.id,
              title: f.name,
              sub: "File",
              href: `/teams/${f.team_id}?file=${f.id}`,
            });
          }
        } catch {
          /* search endpoint may not exist yet; silently skip */
        }
        // Current user pinned at top for quick "go to me".
        if (me.data) {
          const score = fuzzy(term, me.data.display_name) ?? fuzzy(term, me.data.email);
          if (score !== null) {
            out.push({
              kind: "person",
              id: me.data.id,
              title: me.data.display_name,
              sub: "You",
              href: "/me",
            });
          }
        }
        // Actions always shown when matched.
        for (const a of ACTIONS) {
          const s = fuzzy(term, a.title);
          if (s !== null) out.push(a);
        }
        // Dedupe + sort by title score (cheap: by kind then title).
        out.sort((a, b) => a.title.localeCompare(b.title));
        setHits(out.slice(0, 30));
      } finally {
        if (!ctl.signal.aborted) setLoading(false);
      }
    })();
    return () => ctl.abort();
  }, [q, open, teams.data, me.data]);

  const items = useMemo(() => {
    if (!q.trim()) {
      // Default view: actions + shortcuts help.
      return [...ACTIONS.filter((a) => a.id !== "shortcuts")];
    }
    return hits;
  }, [hits, q]);

  useEffect(() => {
    if (active >= items.length) setActive(0);
  }, [items, active]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => Math.min(items.length - 1, a + 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => Math.max(0, a - 1));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const it = items[active];
        if (it) {
          if (it.kind === "action") it.run();
          else nav(it.href);
          setOpen(false);
        }
        return;
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, items, active, nav]);

  if (!open) return null;

  return (
    <div
      className="palette-backdrop flex items-start justify-center pt-[10vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={(e) => {
        if (e.target === e.currentTarget) setOpen(false);
      }}
    >
      <div className="surface-raised w-full max-w-xl shadow-md">
        {showShortcuts ? (
          <div className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-h2">Keyboard shortcuts</h3>
              <button className="btn-ghost btn-sm" onClick={() => setShowShortcuts(false)}>
                Back
              </button>
            </div>
            <ul className="divide-y divide-line">
              {SHORTCUTS.map((s) => (
                <li key={s.keys} className="flex items-center justify-between py-2">
                  <span className="text-meta">{s.label}</span>
                  <kbd className="text-xs font-mono px-1.5 py-0.5 rounded border border-line bg-paper-muted">
                    {s.keys}
                  </kbd>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <>
            <div className="flex items-center border-b border-line px-4 py-3 gap-2">
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
                <circle cx="7" cy="7" r="4.5" />
                <path d="M10.5 10.5l3 3" />
              </svg>
              <input
                autoFocus
                className="flex-1 bg-transparent outline-none text-base text-ink placeholder:text-ink-faint"
                placeholder="Search teams, projects, tasks, people — or run an action…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
              <button
                className="btn-ghost btn-sm"
                onClick={() => setShowShortcuts(true)}
                aria-label="Show shortcuts"
                title="Show shortcuts"
              >
                ?
              </button>
            </div>
            <ul role="listbox" className="max-h-80 overflow-y-auto p-1">
              {loading && (
                <li className="px-3 py-2 text-meta">Searching…</li>
              )}
              {!loading && items.length === 0 && q.trim() && (
                <li className="px-3 py-6 text-center text-meta">
                  No matches. Try a team name or a task title.
                </li>
              )}
              {!loading &&
                items.map((it, i) => (
                  <li
                    key={`${it.kind}-${it.id}`}
                    role="option"
                    aria-selected={i === active}
                    className={`flex items-center gap-3 px-3 py-2 rounded cursor-pointer ${
                      i === active ? "bg-paper-sun" : "hover:bg-paper-muted"
                    }`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => {
                      if (it.kind === "action") it.run();
                      else nav(it.href);
                      setOpen(false);
                    }}
                  >
                    <KindBadge kind={it.kind} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-ink truncate">{it.title}</div>
                      <div className="text-faint truncate">{it.sub}</div>
                    </div>
                    {it.kind === "action" && (
                      <span className="text-faint">Action</span>
                    )}
                  </li>
                ))}
            </ul>
            <div className="border-t border-line px-3 py-2 text-faint flex items-center justify-between">
              <span>↑↓ to move · Enter to run · Esc to close</span>
              <span>
                <kbd className="font-mono">?</kbd> for all shortcuts
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function KindBadge({ kind }: { kind: Hit["kind"] }) {
  const map: Record<Hit["kind"], string> = {
    team: "T",
    project: "P",
    task: "✓",
    person: "@",
    action: "→",
  };
  return (
    <span
      className="w-6 h-6 inline-flex items-center justify-center rounded-md bg-paper-muted border border-line text-ink-muted text-xs font-mono"
      aria-hidden="true"
    >
      {map[kind]}
    </span>
  );
}
