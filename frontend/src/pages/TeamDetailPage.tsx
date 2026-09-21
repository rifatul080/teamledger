// Team detail: projects + invite + chat link.
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useCreateProject, useInviteMember, useTeam, useTeamProjects } from "../app/routes";
import { Button, Card, ErrorBox, Input, Label, Select } from "../components/ui";

export default function TeamDetailPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const team = useTeam(teamId);
  const projects = useTeamProjects(teamId);
  const invite = useInviteMember(teamId ?? "");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"leader" | "member">("member");
  const [error, setError] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectKind, setProjectKind] = useState<"general" | "paper">("general");

  const createProject = useCreateProject(teamId ?? "");

  async function submitInvite(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await invite.mutateAsync({ email, role });
      setEmail("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function submitProject(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createProject.mutateAsync({
        kind: projectKind,
        name: projectName,
        participant_user_ids: [],
      });
      setProjectName("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{team.data?.name ?? "Team"}</h1>

      <Card>
        <h2 className="text-sm font-semibold mb-2">Create a project</h2>
        <form className="flex gap-2 items-end" onSubmit={submitProject}>
          <div className="flex-1">
            <Label htmlFor="proj_name">Name</Label>
            <Input
              id="proj_name"
              required
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="kind">Kind</Label>
            <Select
              id="kind"
              value={projectKind}
              onChange={(e) => setProjectKind(e.target.value as "general" | "paper")}
            >
              <option value="general">General</option>
              <option value="paper">Paper</option>
            </Select>
          </div>
          <Button type="submit" disabled={createProject.isPending}>
            Create
          </Button>
        </form>
        <ErrorBox message={error ?? undefined} />
      </Card>

      <Card>
        <h2 className="text-sm font-semibold mb-2">Projects</h2>
        {projects.isLoading ? (
          <div className="text-slate-500">Loading…</div>
        ) : projects.data && projects.data.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {projects.data.map((p) => (
              <li key={p.id} className="flex items-center justify-between border-b pb-2">
                <Link to={`/projects/${p.id}`} className="text-blue-700 underline">
                  {p.name}
                </Link>
                <span className="text-xs text-slate-500">{p.kind}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-slate-500">No projects yet.</div>
        )}
      </Card>

      <Card>
        <h2 className="text-sm font-semibold mb-2">Invite member</h2>
        <form className="flex gap-2 items-end" onSubmit={submitInvite}>
          <div className="flex-1">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="role">Role</Label>
            <Select id="role" value={role} onChange={(e) => setRole(e.target.value as "leader" | "member")}>
              <option value="member">Member</option>
              <option value="leader">Leader</option>
            </Select>
          </div>
          <Button type="submit" disabled={invite.isPending}>
            Invite
          </Button>
        </form>
        <ErrorBox message={error ?? undefined} />
      </Card>

      <Card>
        <Link to={`/teams/${teamId}/chat`} className="text-blue-700 underline">
          Open chat →
        </Link>
      </Card>
    </div>
  );
}
