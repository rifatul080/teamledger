import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ActivityKind,
  useActivity,
  useMarkActivityRead,
} from "../app/notifications";
import { EmptyState } from "../components/ui/EmptyState";

type TabKey = "all" | ActivityKind;

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "mention", label: "Mentions" },
  { key: "thread_reply", label: "Replies" },
  { key: "reaction", label: "Reactions" },
  { key: "task_assigned", label: "Tasks" },
  { key: "task_reviewed", label: "Reviews" },
  { key: "milestone", label: "Milestones" },
];

export default function NotificationsPage() {
  const [tab, setTab] = useState<TabKey>("all");
  const activity = useActivity();
  const markRead = useMarkActivityRead();
  const items = activity.data?.items ?? [];

  const filtered = useMemo(
    () => (tab === "all" ? items : items.filter((i) => i.kind === tab)),
    [items, tab],
  );

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-h1">Activity</h1>
          <p className="text-meta">Mentions, thread replies, and reactions — all in one feed.</p>
        </div>
        <button
          className="btn-secondary"
          onClick={() => markRead.mutate({ all: true })}
        >
          Mark all read
        </button>
      </header>

      <div className="flex gap-1 flex-wrap border-b border-line">
        {TABS.map((t) => {
          const count = t.key === "all"
            ? (activity.data?.by_kind
                ? Object.values(activity.data.by_kind).reduce((a, b) => a + b, 0)
                : items.filter((i) => !i.read).length)
            : (activity.data?.by_kind?.[t.key as ActivityKind] ?? 0);
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`btn-ghost btn-sm border-b-2 ${
                tab === t.key
                  ? "border-b-accent text-ink"
                  : "border-b-transparent text-ink-muted"
              }`}
            >
              {t.label}
              {count > 0 && (
                <span className="ml-2 inline-flex items-center justify-center text-[10px] font-semibold bg-paper-sun text-ink-muted rounded-full px-1.5 min-w-[1.25rem]">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          title={tab === "all" ? "Nothing to see yet." : `No ${tab} activity.`}
          body="When something happens, it shows up here."
        />
      ) : (
        <ul className="flex flex-col divide-y divide-line card">
          {filtered.map((it) => (
            <li key={it.id} className="py-3 flex items-center gap-3">
              <KindIcon kind={it.kind} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-ink">{it.body}</div>
                <div className="text-faint">
                  {new Date(it.created_at).toLocaleString()}
                </div>
              </div>
              {it.href && (
                <Link
                  to={it.href}
                  className="btn-ghost btn-sm"
                  onClick={() => markRead.mutate({ ids: [it.id] })}
                >
                  Open
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function KindIcon({ kind }: { kind: string }) {
  const glyph = {
    mention: "@",
    thread_reply: "→",
    reaction: "♥",
    task_assigned: "✓",
    task_reviewed: "✓",
    milestone: "★",
    member: "○",
    system: "i",
  }[kind] || "•";
  return (
    <span className="inline-flex items-center justify-center w-7 h-7 rounded-md border border-line bg-paper-muted text-ink-muted font-mono">
      {glyph}
    </span>
  );
}
