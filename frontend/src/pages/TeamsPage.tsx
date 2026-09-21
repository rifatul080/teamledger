// Teams list + create.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useCreateTeam, useTeams } from "../app/routes";
import { Button, Card, ErrorBox, Input, Label } from "../components/ui";

export default function TeamsPage() {
  const teams = useTeams();
  const create = useCreateTeam();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({ name });
      setName("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Teams</h1>

      <Card>
        <h2 className="text-sm font-semibold mb-2">Create a team</h2>
        <form className="flex gap-2 items-end" onSubmit={submit}>
          <div className="flex-1">
            <Label htmlFor="team_name">Name</Label>
            <Input
              id="team_name"
              required
              minLength={1}
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={create.isPending}>
            Create
          </Button>
        </form>
        <ErrorBox message={error ?? undefined} />
      </Card>

      <Card>
        <h2 className="text-sm font-semibold mb-2">Your teams</h2>
        {teams.isLoading ? (
          <div className="text-slate-500">Loading…</div>
        ) : teams.data && teams.data.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {teams.data.map((t) => (
              <li key={t.id} className="flex items-center justify-between border-b pb-2">
                <Link to={`/teams/${t.id}`} className="text-blue-700 underline">
                  {t.name}
                </Link>
                <span className="text-xs text-slate-500">
                  {t.role ?? "member"}{t.archived ? " · archived" : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-slate-500">No teams yet. Create one above.</div>
        )}
      </Card>
    </div>
  );
}
