import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useCreateGoal,
  useCreateMilestone,
  useCreateTask,
  useCreditCategories,
  useProject,
  useProjectGoals,
  useProjectMilestones,
  useProjectParticipants,
  useProjectTasks,
  useTeamMembers,
  useUpdateTaskStatus,
  Task,
} from "../app/data";
import { useMe } from "../app/auth";
import { EmptyState } from "../components/ui/EmptyState";
import { Modal } from "../components/ui/Modal";
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
  const me = useMe();
  const project = useProject(projectId);
  const goals = useProjectGoals(projectId);
  const tasks = useProjectTasks(projectId);
  const update = useUpdateTaskStatus(projectId);
  const [view, setView] = useState<ViewMode>(() => {
    const saved = localStorage.getItem(`tl.view.${projectId}`);
    return (saved as ViewMode) ?? "board";
  });

  // Assignment + planning
  const participants = useProjectParticipants(projectId);
  const milestones = useProjectMilestones(goals.data);
  const members = useTeamMembers(project.data?.team_id);
  const categories = useCreditCategories();
  const createTask = useCreateTask(projectId);
  const createGoal = useCreateGoal(projectId ?? "");
  const createMilestone = useCreateMilestone(projectId ?? "");
  const [taskOpen, setTaskOpen] = useState(false);
  const [goalOpen, setGoalOpen] = useState(false);
  const [milestoneOpen, setMilestoneOpen] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    milestone_id: "",
    assignee_user_id: "",
    category_code: "",
    weight: "1",
    est_hours: "1",
    start_date: new Date().toISOString().slice(0, 10),
    due_date: "",
  });
  const [goalForm, setGoalForm] = useState({ title: "", description: "", target_date: "" });
  const [msForm, setMsForm] = useState({ goal_id: "", title: "", due_date: "" });

  const nameById = useMemo(
    () => new Map((members.data ?? []).map((m) => [m.user_id, m.display_name])),
    [members.data],
  );
  const assignees = useMemo(
    () =>
      (participants.data ?? [])
        .map((id) => ({ id, name: nameById.get(id) ?? "Member" }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [participants.data, nameById],
  );
  const myId = me.data?.id;
  // Default the assignee to you when you contribute to the project.
  const defaultAssignee =
    assignees.find((a) => a.id === myId)?.id ?? assignees[0]?.id ?? "";

  if (!projectId) return null;
  if (project.isLoading) return <div className="text-meta">Loading project…</div>;
  if (!project.data) return <EmptyState title="Project not found" />;

  const allTasks = tasks.data ?? [];

  function changeView(v: ViewMode) {
    setView(v);
    if (projectId) localStorage.setItem(`tl.view.${projectId}`, v);
  }

  const canManage = milestones.length > 0 && assignees.length > 0;

  async function submitTask() {
    if (!form.title.trim() || !form.milestone_id || !form.assignee_user_id) {
      pushToast({
        kind: "error",
        title: "Missing details",
        body: "Title, milestone and assignee are required.",
      });
      return;
    }
    if (!form.due_date) {
      pushToast({ kind: "error", title: "Pick a due date", body: "Tasks need a deadline." });
      return;
    }
    try {
      await createTask.mutateAsync({
        milestone_id: form.milestone_id,
        assignee_user_id: form.assignee_user_id,
        title: form.title.trim(),
        description: form.description || undefined,
        category_code: form.category_code || "software",
        weight: Number(form.weight) || 1,
        est_hours: Number(form.est_hours) || 1,
        start_date: form.start_date,
        due_date: form.due_date,
      });
      pushToast({
        kind: "ok",
        title: "Task assigned",
        body: `${nameById.get(form.assignee_user_id) ?? "Your teammate"} gets a notification and an email.`,
      });
      setTaskOpen(false);
      setForm((f) => ({ ...f, title: "", description: "", due_date: "" }));
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Could not create task",
        body: e instanceof Error ? e.message : "Please try again.",
      });
    }
  }

  async function submitGoal() {
    if (!goalForm.title.trim()) return;
    try {
      await createGoal.mutateAsync({
        title: goalForm.title.trim(),
        description: goalForm.description || undefined,
        target_date: goalForm.target_date || undefined,
      });
      pushToast({ kind: "ok", title: "Goal added" });
      setGoalOpen(false);
      setGoalForm({ title: "", description: "", target_date: "" });
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Could not create goal",
        body: e instanceof Error ? e.message : "Please try again.",
      });
    }
  }

  async function submitMilestone() {
    if (!msForm.goal_id || !msForm.title.trim()) {
      pushToast({ kind: "error", title: "Pick a goal and a title" });
      return;
    }
    const milestone = await createMilestone.mutateAsync({
      goal_id: msForm.goal_id,
      title: msForm.title.trim(),
      due_date: msForm.due_date || undefined,
    }).catch(() => null);
    if (milestone) {
      pushToast({ kind: "ok", title: "Milestone added" });
      setMilestoneOpen(false);
      setMsForm({ goal_id: "", title: "", due_date: "" });
    }
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
          <button className="btn-secondary" onClick={() => setGoalOpen(true)}>
            New goal
          </button>
          <button
            className="btn-primary"
            onClick={() => {
              setForm((f) => ({
                ...f,
                milestone_id: f.milestone_id || milestones[0]?.id || "",
                assignee_user_id: f.assignee_user_id || defaultAssignee,
              }));
              setTaskOpen(true);
            }}
            disabled={!canManage}
            title={
              canManage
                ? undefined
                : "A project needs a milestone and at least one participant before tasks can be assigned."
            }
          >
            Assign task
          </button>
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
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-h2">Goals & milestones</h2>
          <button
            className="btn-ghost btn-sm"
            onClick={() => {
              setMsForm({ goal_id: goals.data?.[0]?.id ?? "", title: "", due_date: "" });
              setMilestoneOpen(true);
            }}
            disabled={(goals.data?.length ?? 0) === 0}
          >
            Add milestone
          </button>
        </div>
        {(goals.data?.length ?? 0) === 0 ? (
          <EmptyState
            title="No goals yet."
            body="Goals give the project a north star; milestones are the checkpoints."
            action={
              <button className="btn-primary" onClick={() => setGoalOpen(true)}>
                Add a goal
              </button>
            }
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

      <Modal open={taskOpen} onClose={() => setTaskOpen(false)} title="Assign a task" size="lg">
        {milestones.length === 0 ? (
          <EmptyState
            title="Add a milestone first"
            body="Tasks live inside a milestone, which lives inside a goal."
            action={
              <button
                className="btn-primary"
                onClick={() => {
                  setTaskOpen(false);
                  setGoalOpen(true);
                }}
              >
                Create a goal
              </button>
            }
          />
        ) : (
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm">
              Title
              <input
                className="input"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="Draft the results section"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Details
              <textarea
                className="input min-h-[4rem]"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="What does done look like?"
              />
            </label>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-sm">
                Milestone
                <select
                  className="input"
                  value={form.milestone_id}
                  onChange={(e) => setForm({ ...form, milestone_id: e.target.value })}
                >
                  <option value="">Choose a milestone…</option>
                  {milestones.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.title} — {m.goal_title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Assign to
                <select
                  className="input"
                  value={form.assignee_user_id}
                  onChange={(e) => setForm({ ...form, assignee_user_id: e.target.value })}
                >
                  <option value="">Choose a teammate…</option>
                  {assignees.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-sm">
                Start
                <input
                  type="date"
                  className="input"
                  value={form.start_date}
                  onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Due
                <input
                  type="date"
                  className="input"
                  value={form.due_date}
                  onChange={(e) => setForm({ ...form, due_date: e.target.value })}
                />
              </label>
            </div>
            <div className="grid sm:grid-cols-3 gap-3">
              <label className="flex flex-col gap-1 text-sm">
                Contribution
                <select
                  className="input"
                  value={form.category_code}
                  onChange={(e) => setForm({ ...form, category_code: e.target.value })}
                >
                  {(categories.data ?? []).map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Weight
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  className="input"
                  value={form.weight}
                  onChange={(e) => setForm({ ...form, weight: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Est. hours
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  className="input"
                  value={form.est_hours}
                  onChange={(e) => setForm({ ...form, est_hours: e.target.value })}
                />
              </label>
            </div>
            <p className="text-meta">

      <Modal open={goalOpen} onClose={() => setGoalOpen(false)} title="New goal">
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Title
            <input
              className="input"
              value={goalForm.title}
              onChange={(e) => setGoalForm({ ...goalForm, title: e.target.value })}
              placeholder="Submit the camera-ready version"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Details
            <textarea
              className="input min-h-[4rem]"
              value={goalForm.description}
              onChange={(e) => setGoalForm({ ...goalForm, description: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Target date
            <input
              type="date"
              className="input"
              value={goalForm.target_date}
              onChange={(e) => setGoalForm({ ...goalForm, target_date: e.target.value })}
            />
          </label>
          <div className="flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setGoalOpen(false)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => void submitGoal()}
              disabled={createGoal.isPending}
            >
              Add goal
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={milestoneOpen} onClose={() => setMilestoneOpen(false)} title="New milestone">
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Goal
            <select
              className="input"
              value={msForm.goal_id}
              onChange={(e) => setMsForm({ ...msForm, goal_id: e.target.value })}
            >
              <option value="">Choose a goal…</option>
              {(goals.data ?? []).map((g) => (
                <option key={g.id} value={g.id}>
                  {g.title}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Title
            <input
              className="input"
              value={msForm.title}
              onChange={(e) => setMsForm({ ...msForm, title: e.target.value })}
              placeholder="Experiments complete"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Due
            <input
              type="date"
              className="input"
              value={msForm.due_date}
              onChange={(e) => setMsForm({ ...msForm, due_date: e.target.value })}
            />
          </label>
          <div className="flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setMilestoneOpen(false)}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => void submitMilestone()}
              disabled={createMilestone.isPending}
            >
              Add milestone
            </button>
          </div>
        </div>
      </Modal>

              The assignee gets an in-app notification and an email with the deadline.
            </p>
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={() => setTaskOpen(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={() => void submitTask()}
                disabled={createTask.isPending}
              >
                {createTask.isPending ? "Assigning…" : "Assign task"}
              </button>
            </div>
          </div>
        )}
      </Modal>

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
