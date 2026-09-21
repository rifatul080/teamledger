// Project detail: goals, milestones, tasks, and a link to scoring view.
import { Link, useParams } from "react-router-dom";
import { useProject, useProjectGoals } from "../app/routes";
import { Card } from "../components/ui";
import { useProjectScore } from "../app/scoring";

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useProject(projectId);
  const goals = useProjectGoals(projectId);
  const score = useProjectScore(projectId);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{project.data?.name ?? "Project"}</h1>
        <div className="flex gap-2 text-sm">
          <Link to={`/projects/${projectId}/score`} className="text-blue-700 underline">
            Author order
          </Link>
        </div>
      </div>

      {score.data && (
        <Card>
          <h2 className="text-sm font-semibold mb-2">Live scoring preview</h2>
          <p className="text-sm text-slate-600">
            {score.data.participants.length} participants ·{" "}
            <span className="font-mono">{score.data.formula_version}</span>
          </p>
          <ul className="mt-2 text-sm">
            {score.data.suggested_order.map((p) => (
              <li key={p.user_id}>
                {p.position}. {p.user_id}
                {p.suggested && <span className="text-xs text-slate-500 ml-1">(suggested)</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <h2 className="text-sm font-semibold mb-2">Goals</h2>
        {goals.isLoading ? (
          <div className="text-slate-500">Loading…</div>
        ) : goals.data && goals.data.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {goals.data.map((g) => (
              <li key={g.id} className="border-b pb-2">
                <Link to={`/projects/${projectId}/goals/${g.id}`} className="text-blue-700 underline">
                  {g.title}
                </Link>
                <span className="text-xs text-slate-500 ml-2">
                  {g.progress_pct.toFixed(0)}% complete
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-slate-500">No goals yet.</div>
        )}
      </Card>
    </div>
  );
}
