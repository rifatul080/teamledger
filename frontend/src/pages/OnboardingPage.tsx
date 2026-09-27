// One-step team creation. The old 5-step CRediT wizard collected the same
// categories/weights that the backend can derive from a work type, so we keep a
// single optional "kind of work" choice and drop the rest.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe } from "../app/auth";
import { PRESETS, WORK_TYPES, useCreateTeam, useTeams, WorkType } from "../app/data";
import { pushToast } from "../components/ui/Toast";

export default function OnboardingPage() {
  const me = useMe();
  const teams = useTeams();
  const createTeam = useCreateTeam();
  const nav = useNavigate();

  const isFirstTeam = isFirstTeamNow(teams.data, me.data?.id);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [workType, setWorkType] = useState<WorkType | "">("");
  const [started, setStarted] = useState(false);

  useEffect(() => {
    setStarted(true);
  }, []);

  if (!started) return null;
  if (!isFirstTeam) return <AlreadyOnATeam />;

  const preset = workType ? PRESETS[workType] : null;

  async function catch_(e: unknown) {
    pushToast({
      kind: "error",
      title: "Couldn't create team",
      body: e instanceof Error ? e.message : "Please try again.",
    });
  }

  async function submit() {
    if (!name.trim()) {
      pushToast({ kind: "error", title: "Name your team" });
      return;
    }
    try {
      const t = await createTeam.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
        work_type: workType || undefined,
        category_preset: workType || undefined,
        categories: preset?.categories.map((c) => c.code),
      });
      pushToast({ kind: "ok", title: "Team created", body: "Now bring your team in." });
      // Land on the members panel with the invite link already generated.
      nav(`/teams/${t.id}?invite=1`);
    } catch (e) {
      await catch_(e);
    }
  }

  return (
    <div className="mx-auto max-w-xl flex flex-col gap-6">
      <header>
        <h1 className="text-h1">Create your team</h1>
        <p className="text-meta">
          A team is one workspace: members, projects, goals, tasks and chat.
        </p>
      </header>

      <form
        className="card flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="label">Team name</span>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Lab Notebooks"
            autoFocus
            required
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="label">What are you working on? (optional)</span>
          <input
            className="input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="One line so teammates know the context."
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="label">Kind of work (optional)</span>
          <select
            className="input"
            value={workType}
            onChange={(e) => setWorkType(e.target.value as WorkType | "")}
          >
            <option value="">Just set it up — I'll decide later</option>
            {WORK_TYPES.map((w) => (
              <option key={w.value} value={w.value}>
                {w.label}
              </option>
            ))}
          </select>
          <span className="text-faint text-xs">
            This only pre-fills the contribution categories used when scoring
            author order. You can change them any time in project settings.
          </span>
        </label>

        <button className="btn-primary self-start" disabled={createTeam.isPending}>
          {createTeam.isPending ? "Creating…" : "Create team"}
        </button>
      </form>

      <p className="text-meta">
        Already have an invite link? Open it and you'll join the team directly.
      </p>
    </div>
  );
}

function isFirstTeamNow(
  teams: { id: string }[] | undefined,
  _meId: string | undefined,
): boolean {
  return (teams?.length ?? 0) === 0;
}

function AlreadyOnATeam() {
  const nav = useNavigate();
  const teams = useTeams();
  const first = teams.data?.[0];
  return (
    <div className="mx-auto max-w-xl flex flex-col gap-4">
      <h1 className="text-h1">You're already on a team</h1>
      <p className="text-meta">Create another one, or head back to your teams.</p>
      <div className="flex gap-2">
        <button className="btn-primary" onClick={() => first && nav(`/teams/${first.id}`)}>
          Open {first?.name ?? "team"}
        </button>
        <button className="btn-secondary" onClick={() => nav("/teams")}>
          All teams
        </button>
      </div>
    </div>
  );
}
