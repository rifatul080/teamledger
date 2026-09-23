import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMe } from "../app/auth";
import {
  useAcceptInvite,
  useInvitationPreview,
} from "../app/data";
import { pushToast } from "../components/ui/Toast";

export default function AcceptInvitePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const me = useMe();
  const preview = useInvitationPreview(token);
  const accept = useAcceptInvite();

  const [error, setError] = useState<string | null>(null);
  const [acceptedTeamId, setAcceptedTeamId] = useState<string | null>(null);

  // If the user lands here while logged-out, send them to /signup carrying
  // the token. After signup they return here and we auto-accept.
  useEffect(() => {
    if (me.isLoading) return;
    if (!me.data && !acceptedTeamId && !error && !preview.isLoading) {
      // Save the token in localStorage so the signup flow can pick it up
      // even after the user closes the tab or comes back.
      try {
        if (token) localStorage.setItem("pending_invite_token", token);
      } catch {
        /* ignore storage errors */
      }
    }
  }, [me.isLoading, me.data, acceptedTeamId, error, preview.isLoading, token]);

  if (!token) {
    return (
      <main className="max-w-md mx-auto card">
        <h1 className="text-h1 mb-2">Invalid invite link</h1>
        <p className="text-body mb-4">
          That link is missing the invite token. Ask whoever shared it to send
          it again.
        </p>
        <Link to="/" className="btn-secondary">Home</Link>
      </main>
    );
  }

  if (preview.isLoading) {
    return (
      <main className="max-w-md mx-auto card">
        <p className="text-meta">Loading invite…</p>
      </main>
    );
  }

  if (preview.isError || !preview.data) {
    return (
      <main className="max-w-md mx-auto card">
        <h1 className="text-h1 mb-2">Invite not found</h1>
        <p className="text-body mb-4">
          This invite link is invalid, expired, or has already been used.
        </p>
        <Link to="/" className="btn-secondary">Home</Link>
      </main>
    );
  }

  const inv = preview.data;

  // Logged-out path: prompt them to sign up or log in.
  if (!me.isLoading && !me.data) {
    return (
      <main className="max-w-md mx-auto card">
        <h1 className="text-h1 mb-2">You're invited to join</h1>
        <p className="text-h2 mb-3">{inv.team_name}</p>
        {inv.team_description && (
          <p className="text-body mb-4">{inv.team_description}</p>
        )}
        <p className="text-meta mb-4">
          Create an account to join this team. You'll be added automatically
          after sign-up.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/signup?next=${encodeURIComponent(`/accept-invite?token=${token}`)}`}
            className="btn-primary"
          >
            Sign up to join
          </Link>
          <Link
            to={`/login?next=${encodeURIComponent(`/accept-invite?token=${token}`)}`}
            className="btn-secondary"
          >
            I already have an account
          </Link>
        </div>
      </main>
    );
  }

  if (acceptedTeamId) {
    return (
      <main className="max-w-md mx-auto card">
        <h1 className="text-h1 mb-2">Welcome to {inv.team_name}</h1>
        <p className="text-body mb-4">You've been added to the team.</p>
        <Link to={`/teams/${acceptedTeamId}`} className="btn-primary">
          Open the team
        </Link>
      </main>
    );
  }

  async function onAccept() {
    setError(null);
    try {
      const r = await accept.mutateAsync(token);
      setAcceptedTeamId(r.team_id);
      pushToast({ kind: "ok", title: `Joined ${inv.team_name}` });
      // Auto-navigate after a brief moment so the toast is visible.
      window.setTimeout(() => navigate(`/teams/${r.team_id}`), 600);
    } catch (e) {
      const err = e as { message?: string };
      setError(err.message ?? "Could not join the team.");
    }
  }

  // Logged-in path.
  return (
    <main className="max-w-md mx-auto card">
      <h1 className="text-h1 mb-2">You're invited to join</h1>
      <p className="text-h2 mb-3">{inv.team_name}</p>
      {inv.team_description && (
        <p className="text-body mb-4">{inv.team_description}</p>
      )}
      {error && (
        <div className="text-danger text-sm mb-3" role="alert">
          {error}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn-primary"
          onClick={onAccept}
          disabled={accept.isPending}
        >
          {accept.isPending ? "Joining…" : `Join ${inv.team_name}`}
        </button>
        <Link to="/" className="btn-secondary">No thanks</Link>
      </div>
      <p className="text-faint text-xs mt-3">
        Invite expires {new Date(inv.expires_at).toLocaleString()}.
      </p>
    </main>
  );
}
