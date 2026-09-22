import { Link, useParams } from "react-router-dom";
import { useGoalMilestones, useProject } from "../app/data";
import { EmptyState } from "../components/ui/EmptyState";
import { StatusBadge } from "../components/ui/StatusBadge";

export default function GoalDetailPage() {
  const { projectId, goalId } = useParams();
  const project = useProject(projectId);
  const ms = useGoalMilestones(goalId);
  if (!goalId || !projectId) return null;
  const milestones = ms.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      <header>
        <Link to={`/projects/${projectId}`} className="text-meta underline">
          ← {project.data?.name ?? "Project"}
        </Link>
        <h1 className="text-h1">Goal detail</h1>
      </header>
      {milestones.length === 0 ? (
        <EmptyState
          title="No milestones yet."
          body="Milestones break a goal into checkpoints."
        />
      ) : (
        <ul className="grid sm:grid-cols-2 gap-3">
          {milestones.map((m) => (
            <li key={m.id} className="card">
              <div className="flex items-center justify-between">
                <span className="font-medium">{m.title}</span>
                <StatusBadge status={m.completed_at ? "done" : "todo"} />
              </div>
              {m.due_date && (
                <div className="text-meta">
                  Due {new Date(m.due_date).toLocaleDateString()}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
