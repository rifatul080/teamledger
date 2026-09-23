import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTeam, useTeamProjects } from "../app/data";
import { useActivity } from "../app/notifications";
import { EmptyState } from "../components/ui/EmptyState";
import { MembersPanel } from "../components/team/MembersPanel";

export default function TeamDetailPage() {
  const { teamId } = useParams();
  const [searchParams] = useSearchParams();
  const team = useTeam(teamId);
  const projects = useTeamProjects(teamId);
  const activity = useActivity(teamId);

  if (!teamId) return null;
  if (team.isLoading) return <div className="text-meta">Loading team…</div>;
  if (!team.data) return <EmptyState title="Team not found" body="It may have been archived or removed." />;

  const t = team.data;
  const canManage = t.role === "leader";
  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h1">{t.name}</h1>
          {t.description && <p className="text-meta">{t.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Link to={`/teams/${t.id}/chat`} className="btn-secondary">
            Open chat
          </Link>
        </div>
      </header>

      <div className="grid lg:grid-cols-3 gap-6">
        <section className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-h2">Projects</h2>
            <Link
              to={`/teams/${t.id}/projects/new`}
              className="btn-secondary btn-sm"
            >
              New project
            </Link>
          </div>
          {(projects.data?.length ?? 0) === 0 ? (
            <EmptyState
              title="No projects yet."
              body="A project groups goals and tasks that share a single paper or scope."
              action={
                <Link
                  to={`/teams/${t.id}/projects/new`}
                  className="btn-primary"
                >
                  Create the first project
                </Link>
              }
            />
          ) : (
            <ul className="grid sm:grid-cols-2 gap-3">
              {(projects.data ?? []).map((p) => (
                <li key={p.id} className="surface p-3">
                  <Link to={`/projects/${p.id}`} className="block">
                    <div className="font-medium">{p.name}</div>
                    <div className="text-faint uppercase font-mono">
                      {p.kind}
                      {p.finalized_at ? " · finalized" : ""}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
        <aside className="card">
          <h2 className="text-h2 mb-3">Members</h2>
          <MembersPanel teamId={teamId} canManage={canManage} autoOpenInvite={searchParams.get("invite") === "1"} />
        </aside>
      </div>

      <section className="card">
        <h2 className="text-h2 mb-3">Recent activity</h2>
        {(activity.data?.items ?? []).length === 0 ? (
          <div className="text-meta">Nothing yet.</div>
        ) : (
          <ul className="divide-y divide-line">
            {(activity.data?.items ?? []).slice(0, 12).map((it) => (
              <li key={it.id} className="py-2 flex items-center gap-3">
                <span className="text-meta flex-1">{it.body}</span>
                <span className="text-faint">
                  {new Date(it.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
