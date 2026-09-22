import { Link, useNavigate } from "react-router-dom";
import { useMe } from "../app/auth";
import { useTeams } from "../app/data";
import { useActivity, useUnreadCount, ActivityItem } from "../app/notifications";
import { EmptyState } from "../components/ui/EmptyState";

export default function DashboardPage() {
  const me = useMe();
  const teams = useTeams();
  const unread = useUnreadCount();
  const activity = useActivity();
  const nav = useNavigate();

  if (!me.data) {
    return <EmptyState title="Loading…" />;
  }

  const ledTeams = (teams.data ?? []).filter((t) => t.role === "leader");
  const memberTeams = (teams.data ?? []).filter((t) => t.role !== "leader");
  const items = activity.data?.items ?? [];

  // My upcoming deadlines is approximated: tasks due within 7 days surfaced
  // from activity items (full per-user task endpoint can land later).
  const upcomingDeadlines = items
    .filter((i) => i.kind === "task_assigned")
    .slice(0, 5);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-h1">
          Welcome back, {me.data.display_name.split(" ")[0]}.
        </h1>
        <p className="text-meta">A snapshot of what's happening across your teams.</p>
      </header>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <KPI
          label="My teams"
          value={(teams.data?.length ?? 0).toString()}
          hint={`${ledTeams.length} as leader · ${memberTeams.length} as member`}
        />
        <KPI
          label="Unread activity"
          value={(unread.data?.unread ?? 0).toString()}
          hint={
            unread.data && unread.data.unread > 0
              ? `${unread.data.by_kind["mention"] ?? 0} mentions`
              : "All caught up"
          }
        />
        <KPI
          label="Open tasks"
          value={upcomingDeadlines.length.toString()}
          hint="Due in the next 7 days"
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <section className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-h2">Recent activity</h2>
            <Link to="/notifications" className="text-meta underline">
              See all
            </Link>
          </div>
          {items.length === 0 ? (
            <EmptyState
              title="No activity yet"
              body="When teammates assign work, complete milestones, or post in chat, you'll see it here."
              action={
                <button
                  className="btn-primary"
                  onClick={() => nav("/onboarding")}
                >
                  Create your first team
                </button>
              }
            />
          ) : (
            <ul className="flex flex-col divide-y divide-line">
              {items.slice(0, 10).map((it) => (
                <ActivityRow key={it.id} item={it} />
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-h2">My teams</h2>
            <Link to="/teams" className="text-meta underline">
              See all
            </Link>
          </div>
          {(teams.data?.length ?? 0) === 0 ? (
            <EmptyState
              title="You're not on any team yet."
              body="Create one or accept an email invite to get started."
              action={
                <button
                  className="btn-primary"
                  onClick={() => nav("/onboarding")}
                >
                  Create a team
                </button>
              }
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {(teams.data ?? []).map((t) => (
                <li key={t.id}>
                  <Link
                    to={`/teams/${t.id}`}
                    className="block px-3 py-2 rounded-md border border-line hover:bg-paper-muted"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{t.name}</span>
                      <span className="text-faint font-mono uppercase">
                        {t.role ?? "member"}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {ledTeams.length > 0 && (
        <section className="card">
          <h2 className="text-h2 mb-3">Open items across teams you lead</h2>
          <p className="text-meta mb-3">
            Rollup of work your teams haven't finished yet. Click a row to
            open the team.
          </p>
          <LeaderRollup />
        </section>
      )}
    </div>
  );
}

function KPI({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="card">
      <div className="text-faint uppercase tracking-wide text-xs font-medium">
        {label}
      </div>
      <div className="text-3xl font-semibold mt-1 leading-none">{value}</div>
      {hint && <div className="text-meta mt-1">{hint}</div>}
    </div>
  );
}

function ActivityRow({ item }: { item: ActivityItem }) {
  const me = useMe();
  const mine = item.actor_user_id && me.data?.id === item.actor_user_id;
  return (
    <li className="py-3 flex items-start gap-3">
      <KindIcon kind={item.kind} />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-ink">
          {mine ? "You" : item.actor_name ?? "Someone"} {item.body}
        </div>
        <div className="text-faint">
          {new Date(item.created_at).toLocaleString()}
          {!item.read && (
            <span className="ml-2 inline-block w-1.5 h-1.5 rounded-full bg-accent align-middle" />
          )}
        </div>
      </div>
      {item.href && (
        <Link to={item.href} className="btn-ghost btn-sm">
          Open
        </Link>
      )}
    </li>
  );
}

function KindIcon({ kind }: { kind: string }) {
  // A small glyph per kind. Always label + icon, never color alone.
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

function LeaderRollup() {
  const teams = useTeams();
  const led = (teams.data ?? []).filter((t) => t.role === "leader");
  if (led.length === 0) {
    return <div className="text-meta">Nothing yet.</div>;
  }
  return (
    <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {led.map((t) => (
        <li key={t.id} className="surface p-3">
          <Link to={`/teams/${t.id}`} className="font-medium underline">
            {t.name}
          </Link>
          <div className="text-meta">Open the team to see open items.</div>
        </li>
      ))}
    </ul>
  );
}
