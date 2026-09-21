// MilestoneCard shows the tasks of a single milestone.
import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import {
  useCreateTask,
  useMilestoneTasks,
  useProject,
  useReviewTask,
  useSubmitTask,
  type Task,
} from "../app/routes";
import { Button, ErrorBox, Input, Label, Select } from "./ui";

const CATEGORIES = [
  ["conceptualization", "Conceptualization"],
  ["data_curation", "Data curation"],
  ["formal_analysis", "Formal analysis"],
  ["funding_acquisition", "Funding acquisition"],
  ["investigation", "Investigation"],
  ["methodology", "Methodology"],
  ["project_administration", "Project administration"],
  ["resources", "Resources"],
  ["software", "Software"],
  ["supervision", "Supervision"],
  ["validation", "Validation"],
  ["visualization", "Visualization"],
  ["writing_original_draft", "Writing - original draft"],
  ["writing_review_editing", "Writing - review & editing"],
] as const;

export default function MilestoneCard({ milestoneId }: { milestoneId: string }) {
  const tasks = useMilestoneTasks(milestoneId);
  const project = useProject(useParams<{ projectId: string }>().projectId);
  const createTask = useCreateTask();
  const submitTask = useSubmitTask();
  const reviewTask = useReviewTask();
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<string>("software");
  const [weight, setWeight] = useState<number>(5);
  const [hours] = useState<number>(4);
  const [startDate, setStartDate] = useState<string>("");
  const [dueDate, setDueDate] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const assignee = project.data?.participant_user_ids?.[0];
      if (!assignee) {
        setError("Project has no participants yet.");
        return;
      }
      await createTask.mutateAsync({
        milestone_id: milestoneId,
        assignee_user_id: assignee,
        title,
        category_code: category,
        weight,
        est_hours: hours,
        start_date: startDate,
        due_date: dueDate,
      });
      setTitle("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="mt-3">
      <form className="grid grid-cols-1 sm:grid-cols-6 gap-2 items-end" onSubmit={submit}>
        <div className="sm:col-span-2">
          <Label htmlFor={`title-${milestoneId}`}>Title</Label>
          <Input
            id={`title-${milestoneId}`}
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`cat-${milestoneId}`}>Category</Label>
          <Select id={`cat-${milestoneId}`} value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map(([c, label]) => (
              <option key={c} value={c}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor={`weight-${milestoneId}`}>Weight</Label>
          <Input
            id={`weight-${milestoneId}`}
            type="number"
            min={1}
            max={10}
            value={weight}
            onChange={(e) => setWeight(Number(e.target.value))}
          />
        </div>
        <div>
          <Label htmlFor={`start-${milestoneId}`}>Start</Label>
          <Input
            id={`start-${milestoneId}`}
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`due-${milestoneId}`}>Due</Label>
          <Input
            id={`due-${milestoneId}`}
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </div>
        <div className="sm:col-span-6">
          <Button type="submit" disabled={createTask.isPending}>
            Add task
          </Button>
          <ErrorBox message={error ?? undefined} />
        </div>
      </form>

      <ul className="mt-3 flex flex-col gap-1 text-sm">
        {tasks.data?.map((t) => (
          <TaskRow
            key={t.id}
            task={t}
            onSubmit={() => submitTask.mutate({ id: t.id, note: "" })}
            onAccept={(q) => reviewTask.mutate({ id: t.id, decision: "accept", quality: q })}
            onReject={(q) => reviewTask.mutate({ id: t.id, decision: "reject", quality: q })}
          />
        ))}
      </ul>
    </div>
  );
}

function TaskRow({
  task,
  onSubmit,
  onAccept,
  onReject,
}: {
  task: Task;
  onSubmit: () => void;
  onAccept: (quality: number) => void;
  onReject: (quality: number) => void;
}) {
  return (
    <li className="flex items-center justify-between border-b py-1">
      <div>
        <span className="font-medium">{task.title}</span>
        <span className="text-xs text-slate-500 ml-2">
          {task.category_code} · w={task.weight} · {task.status}
        </span>
      </div>
      <div className="flex gap-1">
        {task.status === "todo" || task.status === "in_progress" || task.status === "needs_rework" ? (
          <Button variant="secondary" onClick={onSubmit}>
            Submit
          </Button>
        ) : null}
        {task.status === "in_review" ? (
          <>
            <Button onClick={() => onAccept(4)}>Accept</Button>
            <Button variant="danger" onClick={() => onReject(2)}>
              Reject
            </Button>
          </>
        ) : null}
      </div>
    </li>
  );
}
