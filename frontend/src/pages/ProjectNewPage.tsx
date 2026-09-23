import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useCreateProject, useTeamMembers } from "../app/data";
import { EmptyState } from "../components/ui/EmptyState";

type Kind = "general" | "paper";
type VenueKind = "journal" | "conference";
type ContribVisibility = "leader_only" | "all";

export default function ProjectNewPage() {
  const { teamId } = useParams();
  const navigate = useNavigate();
  const create = useCreateProject(teamId ?? "");
  const members = useTeamMembers(teamId);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<Kind>("general");
  const [targetVenue, setTargetVenue] = useState("");
  const [venueKind, setVenueKind] = useState<VenueKind>("journal");
  const [deadline, setDeadline] = useState("");
  const [visibility, setVisibility] = useState<ContribVisibility>("leader_only");
  const [reviewerId, setReviewerId] = useState<string>("");
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const leaderId = useMemo(() => {
    const m = (members.data ?? []).find((x) => x.role === "leader");
    return m?.user_id;
  }, [members.data]);

  function toggleParticipant(id: string) {
    setParticipantIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!teamId) return;
    if (!name.trim()) {
      setError("Project name is required.");
      return;
    }
    try {
      const created = await create.mutateAsync({
        kind,
        name: name.trim(),
        description: description.trim() || undefined,
        target_venue: kind === "paper" && targetVenue.trim() ? targetVenue.trim() : undefined,
        venue_kind: kind === "paper" ? venueKind : undefined,
        submission_deadline: kind === "paper" && deadline ? deadline : undefined,
        contrib_visibility: visibility,
        // reviewer_user_id is accepted by the backend but not yet typed on the
        // local Project; cast through unknown to keep the type strict here.
        ...(kind === "paper" && reviewerId
          ? { reviewer_user_id: reviewerId as unknown as never }
          : {}),
        participant_user_ids: participantIds,
      });
      navigate(`/projects/${created.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not create the project.",
      );
    }
  }

  if (!teamId) return null;
  if (members.isLoading) return <div className="text-meta">Loading team…</div>;

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-h1">New project</h1>
          <p className="text-meta">
            A project groups goals and tasks that share a single paper or scope.
          </p>
        </div>
        <Link to={`/teams/${teamId}`} className="btn-secondary btn-sm">
          Cancel
        </Link>
      </header>

      {(members.data ?? []).length === 0 ? (
        <EmptyState
          title="No team members found"
          body="Invite at least one teammate before creating a project."
          action={
            <Link to={`/teams/${teamId}`} className="btn-primary">
              Back to team
            </Link>
          }
        />
      ) : (
        <form onSubmit={onSubmit} className="card flex flex-col gap-4">
          <div>
            <label className="label" htmlFor="kind">
              Kind
            </label>
            <select
              id="kind"
              className="input"
              value={kind}
              onChange={(e) => setKind(e.target.value as Kind)}
            >
              <option value="general">General</option>
              <option value="paper">Paper</option>
            </select>
            <p className="text-faint mt-1">
              Paper projects get venue, deadline, reviewer, and an
              evidence-based contribution record.
            </p>
          </div>

          <div>
            <label className="label" htmlFor="name">
              Name
            </label>
            <input
              id="name"
              required
              maxLength={200}
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. NeurIPS 2026 submission"
            />
          </div>

          <div>
            <label className="label" htmlFor="description">
              Description (optional)
            </label>
            <textarea
              id="description"
              className="input"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short scope or goal for the project."
            />
          </div>

          {kind === "paper" && (
            <>
              <div>
                <label className="label" htmlFor="venue">
                  Target venue
                </label>
                <input
                  id="venue"
                  className="input"
                  value={targetVenue}
                  onChange={(e) => setTargetVenue(e.target.value)}
                  placeholder="e.g. NeurIPS, ICML, JMLR"
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label className="label" htmlFor="venue-kind">
                    Venue type
                  </label>
                  <select
                    id="venue-kind"
                    className="input"
                    value={venueKind}
                    onChange={(e) => setVenueKind(e.target.value as VenueKind)}
                  >
                    <option value="journal">Journal</option>
                    <option value="conference">Conference</option>
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="deadline">
                    Submission deadline
                  </label>
                  <input
                    id="deadline"
                    type="date"
                    className="input"
                    value={deadline}
                    onChange={(e) => setDeadline(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <label className="label" htmlFor="reviewer">
                  Reviewer (optional)
                </label>
                <select
                  id="reviewer"
                  className="input"
                  value={reviewerId}
                  onChange={(e) => setReviewerId(e.target.value)}
                >
                  <option value="">— none —</option>
                  {(members.data ?? [])
                    .filter((m) => m.user_id !== leaderId)
                    .map((m) => (
                      <option key={m.user_id} value={m.user_id}>
                        {m.display_name}
                      </option>
                    ))}
                </select>
                <p className="text-faint mt-1">
                  The reviewer accepts or rejects task submissions. The team
                  leader cannot review.
                </p>
              </div>
            </>
          )}

          <div>
            <label className="label" htmlFor="visibility">
              Contribution visibility
            </label>
            <select
              id="visibility"
              className="input"
              value={visibility}
              onChange={(e) =>
                setVisibility(e.target.value as ContribVisibility)
              }
            >
              <option value="leader_only">Leader only (default)</option>
              <option value="all">All members</option>
            </select>
            <p className="text-faint mt-1">
              When "all members" is on, teammates can see per-task contribution
              weights before the project is finalised.
            </p>
          </div>

          <div>
            <label className="label">Participants</label>
            <ul className="flex flex-col gap-2">
              {(members.data ?? []).map((m) => (
                <li key={m.user_id} className="flex items-center gap-2">
                  <input
                    id={`p-${m.user_id}`}
                    type="checkbox"
                    checked={participantIds.includes(m.user_id)}
                    onChange={() => toggleParticipant(m.user_id)}
                  />
                  <label htmlFor={`p-${m.user_id}`} className="text-sm">
                    {m.display_name}{" "}
                    <span className="text-faint">({m.role})</span>
                  </label>
                </li>
              ))}
            </ul>
            <p className="text-faint mt-1">
              All team members can still join goals. Pick the ones who should
              appear on the contribution record.
            </p>
          </div>

          {error && (
            <div className="text-danger text-sm" role="alert">
              {error}
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="btn-primary"
              disabled={create.isPending}
            >
              {create.isPending ? "Creating…" : "Create project"}
            </button>
            <Link to={`/teams/${teamId}`} className="btn-secondary">
              Cancel
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}
