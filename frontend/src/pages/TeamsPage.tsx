import { Link } from "react-router-dom";
import { useTeams } from "../app/data";
import { EmptyState } from "../components/ui/EmptyState";

export default function TeamsPage() {
  const teams = useTeams();
  const data = teams.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-h1">Teams</h1>
          <p className="text-meta">Each team is its own workspace, with members, projects, and scoring.</p>
        </div>
        <Link to="/onboarding" className="btn-primary">
          New team
        </Link>
      </header>

      {data.length === 0 ? (
        <EmptyState
          title="You're not on any team yet."
          body="Create your first team to start tracking work, or wait for an email invite from a leader."
          action={
            <Link to="/onboarding" className="btn-primary">
              Create your first team
            </Link>
          }
        />
      ) : (
        <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.map((t) => (
            <li key={t.id} className="card hover:border-accent transition">
              <Link to={`/teams/${t.id}`} className="block">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-ink">{t.name}</span>
                  <span className="text-faint font-mono uppercase">
                    {t.role ?? "member"}
                  </span>
                </div>
                {t.description && (
                  <p className="text-meta line-clamp-2">{t.description}</p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
