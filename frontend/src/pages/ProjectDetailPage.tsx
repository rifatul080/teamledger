import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useProject,
  useProjectGoals,
  useProjectTasks,
  useUpdateTaskStatus,
  Task,
} from "../app/data";
import { EmptyState } from "../components/ui/EmptyState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { pushToast } from "../components/ui/Toast";

type ViewMode = "board" | "list" | "calendar" | "timeline";

const VIEW_LABELS: Record<ViewMode, string> = {
  board: "Board",
  list: "List",
  calendar: "Calendar",
  timeline: "Timeline",
};

const COLUMNS: Task["status"][] = [
  "todo",
  "in_progress",
  "in_review",
  "needs_rework",
  "done",
];

export default function ProjectDetailPage() {
  const { projectId } = useParams();
  const project = useProject(projectId);
  const goals = useProjectGoals(projectId);
  const tasks = useProjectTasks(projectId);
  const update = useUpdateTaskStatus(projectId);
  const [view, setView] = useState<ViewMode>(() => {
    const saved = localStorage.getItem(`tl.view.${projectId}`);
    return (saved as ViewMode) ?? "board";
  });

  if (!projectId) return null;
  if (project.isLoading) return <div className="text-meta">Loading project…</div>;
  if (!project.data) return <EmptyState title="Project not found" />;

  const allTasks = tasks.data ?? [];

  function changeView(v: ViewMode) {
    setView(v);
    if (projectId) localStorage.setItem(`tl.view.${projectId}`, v);
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-end justify-between gap-4">
        <div>
          <div className="text-meta uppercase font-mono">
            {project.data.kind}
          </div>
          <h1 className="text-h1">{project.data.name}</h1>
          {project.data.description && (
            <p className="text-meta">{project.data.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Link to={`/projects/${projectId}/scoring`} className="btn-secondary">
            Scoring
          </Link>
          <Link to={`/projects/${projectId}/goals/new`} className="btn-secondary">
            New goal
          </Link>
        </div>
      </header>

      <div className="flex gap-1 border-b border-line" role="tablist">
        {(Object.keys(VIEW_LABELS) as ViewMode[]).map((v) => (
          <button
            key={v}
            role="tab"
            aria-selected={view === v}
            className={`btn-ghost btn-sm border-b-2 ${
              view === v
                ? "border-b-accent text-ink"
                : "border-b-transparent text-ink-muted"
            }`}
            onClick={() => changeView(v)}
          >
            {VIEW_LABELS[v]}
          </button>
        ))}
      </div>

      {view === "board" && <BoardView tasks={allTasks} onChangeStatus={(id, status) => update.mutate({ id, status })} />}
      {view === "list" && <ListView tasks={allTasks} />}
      {(view === "calendar" || view === "timeline") && (
        <TimelineView tasks={allTasks} />
      )}

      <section className="card">
        <h2 className="text-h2 mb-3">Goals</h2>
        {(goals.data?.length ?? 0) === 0 ? (
          <EmptyState
            title="No goals yet."
            body="Goals give the project a north star; milestones are the checkpoints."
            action={<Link to={`/projects/${projectId}/goals/new`} className="btn-primary">Add a goal</Link>}
          />
        ) : (
          <ul className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(goals.data ?? []).map((g) => (
              <li key={g.id} className="surface p-3">
                <Link to={`/projects/${projectId}/goals/${g.id}`} className="block">
                  <div className="font-medium">{g.title}</div>
                  {g.target_date && (
                    <div className="text-faint">
                      Target {new Date(g.target_date).toLocaleDateString()}
                    </div>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function BoardView({
  tasks,
  onChangeStatus,
}: {
  tasks: Task[];
  onChangeStatus: (id: string, status: Task["status"]) => void;
}) {
  const grouped: Record<Task["status"], Task[]> = {
    todo: [], in_progress: [], in_review: [], needs_rework: [], done: [], proposed: [],
  };
  for (const t of tasks) (grouped[t.status] ||= []).push(t);

  const [dragId, setDragId] = useState<string | null>(null);
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 overflow-x-auto">
      {COLUMNS.map((col) => (
        <div
          key={col}
          className="surface p-3 min-h-[200px]"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const id = dragId ?? e.dataTransfer.getData("text/plain");
            if (id) {
              onChangeStatus(id, col);
              pushToast({ kind: "ok", title: "Moved", body: `Task moved to ${col.replace("_", " ")}` });
            }
            setDragId(null);
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <StatusBadge status={col} />
            <span className="text-faint">{grouped[col]?.length ?? 0}</span>
          </div>
          <ul className="flex flex-col gap-2">
            {(grouped[col] ?? []).map((t) => (
              <li
                key={t.id}
                className="card p-3 cursor-grab active:cursor-grabbing"
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData("text/plain", t.id);
                  setDragId(t.id);
                }}
              >
                <div className="text-sm font-medium">{t.title}</div>
                <div className="flex items-center justify-between mt-2 text-faint">
                  <span className="font-mono">{t.category_code}</span>
                  <span>{t.due_date?.slice(0, 10)}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ListView({ tasks }: { tasks: Task[] }) {
  if (tasks.length === 0) {
    return <EmptyState title="No tasks yet." body="Tasks belong to milestones inside a goal." />;
  }
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-meta">
            <th className="p-2 font-medium">Title</th>
            <th className="p-2 font-medium">Status</th>
            <th className="p-2 font-medium">Category</th>
            <th className="p-2 font-medium">Due</th>
            <th className="p-2 font-medium text-right">Weight</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => (
            <tr key={t.id} className="border-t border-line">
              <td className="p-2">{t.title}</td>
              <td className="p-2"><StatusBadge status={t.status} /></td>
              <td className="p-2 font-mono text-faint">{t.category_code}</td>
              <td className="p-2">{t.due_date?.slice(0, 10)}</td>
              <td className="p-2 text-right">{t.weight}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TimelineView({ tasks }: { tasks: Task[] }) {
  // Simple Gantt-style: rows of tasks with a start..end bar.
  if (tasks.length === 0) {
    return <EmptyState title="Nothing to schedule." />;
  }
  const dates = tasks.flatMap((t) => [t.start_date, t.due_date]).filter(Boolean) as string[];
  if (dates.length === 0) return <EmptyState title="No dates set." />;
  const min = new Date(Math.min(...dates.map((d) => new Date(d).getTime())));
  const max = new Date(Math.max(...dates.map((d) => new Date(d).getTime())));
  const total = Math.max(1, max.getTime() - min.getTime());

  return (
    <div className="card overflow-x-auto">
      <div className="min-w-[600px]">
        {tasks.map((t) => {
          const start = new Date(t.start_date).getTime();
          const end = new Date(t.due_date).getTime();
          const left = ((start - min.getTime()) / total) * 100;
          const width = Math.max(2, ((end - start) / total) * 100);
          return (
            <div key={t.id} className="grid grid-cols-[160px_1fr] items-center gap-2 py-1">
              <span className="text-meta truncate">{t.title}</span>
              <div className="relative h-5 bg-paper-muted rounded">
                <span
                  className="absolute top-0 h-5 rounded bg-accent text-white text-[10px] flex items-center justify-center"
                  style={{ left: `${left}%`, width: `${width}%` }}
                >
                  {t.category_code}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
