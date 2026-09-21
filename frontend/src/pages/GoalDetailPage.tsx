// Goal detail: milestones + tasks inside each milestone.
import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { useCreateMilestone, useGoalMilestones, useToggleMilestone, type Milestone } from "../app/routes";
import { Button, Card, ErrorBox, Input, Label } from "../components/ui";
import MilestoneCard from "../components/MilestoneCard";

export default function GoalDetailPage() {
  const { goalId } = useParams<{ goalId: string; projectId: string }>();
  const projectId = useParams<{ projectId: string }>().projectId ?? "";
  const milestones = useGoalMilestones(goalId);
  const create = useCreateMilestone(goalId ?? "", projectId);
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({ title, due_date: dueDate || undefined });
      setTitle("");
      setDueDate("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Goal milestones</h1>

      <Card>
        <h2 className="text-sm font-semibold mb-2">Add milestone</h2>
        <form className="flex gap-2 items-end" onSubmit={submit}>
          <div className="flex-1">
            <Label htmlFor="ms_title">Title</Label>
            <Input id="ms_title" required value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="ms_due">Due date</Label>
            <Input id="ms_due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
          <Button type="submit" disabled={create.isPending}>
            Add
          </Button>
        </form>
        <ErrorBox message={error ?? undefined} />
      </Card>

      <Card>
        <h2 className="text-sm font-semibold mb-2">Milestones</h2>
        {milestones.isLoading ? (
          <div className="text-slate-500">Loading…</div>
        ) : milestones.data && milestones.data.length > 0 ? (
          <ul className="flex flex-col gap-3">
            {milestones.data.map((m) => (
              <li key={m.id}>
                <MilestoneRow milestone={m} projectId={projectId} />
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-slate-500">No milestones yet.</div>
        )}
      </Card>
    </div>
  );
}

function MilestoneRow({ milestone, projectId }: { milestone: Milestone; projectId: string }) {
  const toggle = useToggleMilestone(projectId);
  return (
    <div className="rounded border p-2">
      <div className="flex items-center justify-between">
        <span className="font-medium">{milestone.title}</span>
        <Button
          variant="secondary"
          onClick={() => toggle.mutate({ id: milestone.id, complete: !milestone.completed_at })}
        >
          {milestone.completed_at ? "Reopen" : "Complete"}
        </Button>
      </div>
      {milestone.due_date && (
        <div className="text-xs text-slate-500">Due {milestone.due_date}</div>
      )}
      <MilestoneCard milestoneId={milestone.id} />
    </div>
  );
}
