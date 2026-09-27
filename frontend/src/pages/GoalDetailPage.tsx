import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Milestone,
  Task,
  useCreateMilestone,
  useCreateTask,
  useCreditCategories,
  useGoalMilestones,
  useMilestoneTasks,
  useProject,
  useProjectGoals,
  useProjectParticipants,
  useTeamMembers,
  useToggleMilestone,
  useUpdateTaskStatus,
} from "../app/data";
import { EmptyState } from "../components/ui/EmptyState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { pushToast } from "../components/ui/Toast";

const today = () => new Date().toISOString().slice(0, 10);

type TaskForm = {
  title: string;
  assignee_user_id: string;
  category_code: string;
  due_date: string;
  est_hours: string;
};

const BLANK_TASK: TaskForm = {
  title: "",
  assignee_user_id: "",
  category_code: "",
  due_date: "",
  est_hours: "2",
};

export default function GoalDetailPage() {
  const { projectId, goalId } = useParams();
  const project = useProject(projectId);
  const goals = useProjectGoals(projectId);
  const goal = useMemo(
    () => (goals.data ?? []).find((g) => g.id === goalId) ?? null,
    [goals.data, goalId],
  );
  const milestones = useGoalMilestones(goalId);
  const participants = useProjectParticipants(projectId);
  const members = useTeamMembers(project.data?.team_id);
  const categories = useCreditCategories();
  const createMilestone = useCreateMilestone(projectId ?? "");
  const createTask = useCreateTask(projectId);
  const toggleMilestone = useToggleMilestone(projectId ?? "");
  const updateStatus = useUpdateTaskStatus(projectId);

  const [msForm, setMsForm] = useState({ title: "", due_date: "" });
  const [taskFor, setTaskFor] = useState<string | null>(null);
  const [taskForm, setTaskForm] = useState<TaskForm>(BLANK_TASK);

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

  if (!projectId || !goalId) return null;
  if (project.isLoading || goals.isLoading) {
    return <div className="text-meta">Loading goalâ€¦</div>;
  }
  if (!goal) return <EmptyState title="Goal not found" />;

  const rows = milestones.data ?? [];

  async function addMilestone() {
    if (!msForm.title.trim()) {
      pushToast({ kind: "error", title: "Give the milestone a title" });
      return;
    }
    try {
      await createMilestone.mutateAsync({
        goal_id: goalId as string,
        title: msForm.title.trim(),
        due_date: msForm.due_date || undefined,
      });
      pushToast({ kind: "ok", title: "Milestone added" });
      setMsForm({ title: "", due_date: "" });
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Could not add milestone",
        body: e instanceof Error ? e.message : "Please try again.",
      });
    }
  }

  async function addTask(milestoneId: string) {
    if (!taskForm.title.trim() || !taskForm.assignee_user_id) {
      pushToast({ kind: "error", title: "Title and assignee are required" });
      return;
    }
    if (!taskForm.due_date) {
      pushToast({ kind: "error", title: "Pick a due date" });
      return;
    }
    try {
      await createTask.mutateAsync({
        milestone_id: milestoneId,
        assignee_user_id: taskForm.assignee_user_id,
        title: taskForm.title.trim(),
        category_code: taskForm.category_code || "software",
        weight: 1,
        est_hours: Number(taskForm.est_hours) || 1,
        start_date: today(),
        due_date: taskForm.due_date,
      });
      pushToast({
        kind: "ok",
        title: "Task assigned",
        body: `${nameById.get(taskForm.assignee_user_id) ?? "Your teammate"} was notified.`,
      });
      setTaskFor(null);
      setTaskForm(BLANK_TASK);
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Could not create task",
        body: e instanceof Error ? e.message : "Please try again.",
      });
    }
  }


  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to={`/projects/${projectId}`} className="text-meta underline">
            â† {project.data?.name}
          </Link>
          <h1 className="text-h1">{goal.title}</h1>
          {goal.description && <p className="text-meta">{goal.description}</p>}
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold text-ink">
            {Math.round(goal.progress_pct)}%
          </div>
          {goal.target_date && (
            <div className="text-faint">
              Target {new Date(goal.target_date).toLocaleDateString()}
            </div>
          )}
        </div>
      </header>

      <div
        className="h-2 rounded bg-paper-muted overflow-hidden"
        role="progressbar"
        aria-valuenow={Math.round(goal.progress_pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Goal progress"
      >
        <div
          className="h-full bg-accent"
          style={{ width: `${Math.min(100, Math.max(0, goal.progress_pct))}%` }}
        />
      </div>

      <section className="card">
        <h2 className="text-h2 mb-3">New milestone</h2>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 flex-1 min-w-[14rem]">
            <span className="label">Title</span>
            <input
              className="input"
              value={msForm.title}
              onChange={(e) => setMsForm({ ...msForm, title: e.target.value })}
              placeholder="Experiments complete"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="label">Due</span>
            <input
              type="date"
              className="input"
              value={msForm.due_date}
              onChange={(e) => setMsForm({ ...msForm, due_date: e.target.value })}
            />
          </label>
          <button
            className="btn-primary"
            onClick={() => void addMilestone()}
            disabled={createMilestone.isPending}
          >
            {createMilestone.isPending ? "Addingâ€¦" : "Add milestone"}
          </button>
        </div>
      </section>

      {rows.length === 0 ? (
        <EmptyState
          title="No milestones yet"
          body="Milestones are the checkpoints tasks hang off. Add the first one above."
        />
      ) : (
        <ul className="flex flex-col gap-4">
          {rows.map((m) => (
            <li key={m.id} className="card">
              <MilestoneBlock
                milestone={m}
                projectId={projectId as string}
                assignees={assignees}
                categories={(categories.data ?? []).map((c) => c.code)}
                nameById={nameById}
                onToggle={(complete) => toggleMilestone.mutate({ id: m.id, complete })}
                composing={taskFor === m.id}
                onToggleCompose={() => setTaskFor((cur) => (cur === m.id ? null : m.id))}
                form={taskForm}
                setForm={setTaskForm}
                onSubmit={() => void addTask(m.id)}
                pending={createTask.isPending}
                onStatus={(id, status) => updateStatus.mutate({ id, status })}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );


function MilestoneBlock({
  milestone,
  projectId,
  assignees,
  categories,
  nameById,
  onToggle,
  composing,
  onToggleCompose,
  form,
  setForm,
  onSubmit,
  pending,
  onStatus,
}: {
  milestone: Milestone;
  projectId: string;
  assignees: { id: string; name: string }[];
  categories: string[];
  nameById: Map<string, string>;
  onToggle: (complete: boolean) => void;
  composing: boolean;
  onToggleCompose: () => void;
  form: TaskForm;
  setForm: (f: TaskForm) => void;
  onSubmit: () => void;
  pending: boolean;
  onStatus: (id: string, status: Task["status"]) => void;
}) {
  const tasks = useMilestoneTasks(milestone.id);
  const rows = tasks.data ?? [];
  const done = rows.filter((t) => t.status === "done").length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={Boolean(milestone.completed_at)}
              onChange={(e) => onToggle(e.target.checked)}
              aria-label={`Mark ${milestone.title} complete`}
            />
            <span className={milestone.completed_at ? "line-through text-faint" : "font-medium"}>
              {milestone.title}
            </span>
          </label>
          {milestone.due_date && (
            <span className="text-faint text-xs">
              due {new Date(milestone.due_date).toLocaleDateString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-faint text-xs">
            {done}/{rows.length} done
          </span>
          <button
            className="btn-ghost btn-sm"
            onClick={onToggleCompose}
            disabled={assignees.length === 0}
            title={
              assignees.length === 0
                ? "Add project participants before assigning tasks"
                : undefined
            }
          >
            {composing ? "Close" : "Assign task"}
          </button>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="text-meta text-sm">No tasks in this milestone yet.</div>
      ) : (
        <ul className="flex flex-col gap-1">
          {rows.map((t) => (
            <li key={t.id} className="flex flex-wrap items-center gap-2 text-sm">
              <StatusBadge status={t.status} />
              <Link
                to={`/projects/${projectId}?task=${t.id}`}
                className="hover:text-accent underline decoration-line underline-offset-2"
              >
                {t.title}
              </Link>
              <span className="text-faint text-xs">
                {nameById.get(t.assignee_user_id) ?? "Unassigned"} · due {t.due_date?.slice(0, 10)}
              </span>
              {t.status !== "done" && (
                <button
                  className="btn-ghost btn-xs ml-auto"
                  onClick={() => onStatus(t.id, "done")}
                >
                  Mark done
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {composing && (
        <div className="surface p-3 flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm">
            Task
            <input
              className="input"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="Draft the results section"
            />
          </label>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2">
            <label className="flex flex-col gap-1 text-sm">
              Assign to
              <select
                className="input"
                value={form.assignee_user_id}
                onChange={(e) => setForm({ ...form, assignee_user_id: e.target.value })}
              >
                <option value="">Choose…</option>
                {assignees.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
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
            <label className="flex flex-col gap-1 text-sm">
              Contribution
              <select
                className="input"
                value={form.category_code}
                onChange={(e) => setForm({ ...form, category_code: e.target.value })}
              >
                <option value="">Default</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
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
          <button className="btn-primary btn-sm self-start" onClick={onSubmit} disabled={pending}>
            {pending ? "Assigning…" : "Assign task"}
          </button>
        </div>
      )}
    </div>
  );
}

}