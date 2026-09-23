import { useEffect, useState } from "react";
import { useAddMemberDirect, useCreateInviteLink, useTeamMembers } from "../../app/data";
import { Avatar } from "../ui/Avatar";
import { pushToast } from "../ui/Toast";

type Props = {
  teamId: string;
  /** Whether the current user can add or generate invite links. */
  canManage: boolean;
  /** If true, the invite-link panel is shown open on first mount. */
  autoOpenInvite?: boolean;
};

export function MembersPanel({ teamId, canManage, autoOpenInvite = false }: Props) {
  const members = useTeamMembers(teamId);
  const addMember = useAddMemberDirect(teamId);
  const createLink = useCreateInviteLink(teamId);

  const [showAdd, setShowAdd] = useState(false);
  const [showLink, setShowLink] = useState(false);
  const [autoOpened, setAutoOpened] = useState(false);

  useEffect(() => {
    if (autoOpenInvite && !autoOpened && !linkData) {
      setAutoOpened(true);
      setShowLink(true);
      void onGenerateLink();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOpenInvite, autoOpened]);
  const [email, setEmail] = useState("");
  const [emailErr, setEmailErr] = useState<string | null>(null);
  const [linkData, setLinkData] = useState<{
    url: string;
    expires_at: string;
  } | null>(null);

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    setEmailErr(null);
    try {
      const m = await addMember.mutateAsync({ email: email.trim() });
      pushToast({
        kind: "ok",
        title: "Member added",
        body: `${m.display_name} is now on the team.`,
      });
      setEmail("");
      setShowAdd(false);
    } catch (e2) {
      const err = e2 as { code?: string; message?: string; details?: unknown };
      const code = err.code ?? "";
      if (code === "team.user_unknown") {
        setEmailErr(
          "No TeamLedger account with that email. Use 'Generate invite link' instead and share it with them.",
        );
      } else if (code === "team.already_member") {
        setEmailErr("That person is already on the team.");
      } else if (code === "team.self_add") {
        setEmailErr("You're already on this team.");
      } else {
        setEmailErr(err.message ?? "Could not add member.");
      }
    }
  }

  async function onGenerateLink() {
    try {
      const r = await createLink.mutateAsync();
      setLinkData({ url: r.url, expires_at: r.expires_at });
      setShowLink(true);
      pushToast({
        kind: "ok",
        title: "Invite link created",
        body: "Anyone with the link can join — share it carefully.",
      });
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Could not create link",
        body: (e as { message?: string }).message,
      });
    }
  }

  async function copyLink() {
    if (!linkData) return;
    try {
      await navigator.clipboard.writeText(linkData.url);
      pushToast({ kind: "ok", title: "Link copied to clipboard" });
    } catch {
      pushToast({ kind: "error", title: "Copy failed — select and copy manually." });
    }
  }

  if (!canManage) {
    return (
      <ul className="flex flex-col gap-2">
        {(members.data ?? []).map((m) => (
          <li key={m.user_id} className="flex items-center gap-2">
            <Avatar
              userId={m.user_id}
              displayName={m.display_name}
              src={m.avatar_url ?? null}
              size="sm"
            />
            <div className="min-w-0">
              <div className="text-sm truncate">{m.display_name}</div>
              <div className="text-faint truncate">{m.role}</div>
            </div>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-2">
        {(members.data ?? []).map((m) => (
          <li key={m.user_id} className="flex items-center gap-2">
            <Avatar
              userId={m.user_id}
              displayName={m.display_name}
              src={m.avatar_url ?? null}
              size="sm"
            />
            <div className="min-w-0 flex-1">
              <div className="text-sm truncate">{m.display_name}</div>
              <div className="text-faint truncate">{m.role}</div>
            </div>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-2 pt-2 border-t border-line">
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => {
            setShowAdd((v) => !v);
            setShowLink(false);
          }}
          aria-expanded={showAdd}
        >
          {showAdd ? "Cancel" : "Add member"}
        </button>
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => {
            setShowLink((v) => !v);
            setShowAdd(false);
            if (!showLink && !linkData) void onGenerateLink();
          }}
          disabled={createLink.isPending}
          aria-expanded={showLink}
        >
          {createLink.isPending
            ? "Generating…"
            : showLink
              ? "Hide link"
              : "Generate invite link"}
        </button>
      </div>

      {showAdd && (
        <form onSubmit={onAdd} className="surface p-3 flex flex-col gap-2">
          <label className="label" htmlFor="add-member-email">
            Add an existing TeamLedger user
          </label>
          <input
            id="add-member-email"
            type="email"
            className="input"
            placeholder="teammate@example.org"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <p className="text-faint text-xs">
            Works only if they already have a TeamLedger account. If not,
            use "Generate invite link" to share a sign-up link with them.
          </p>
          {emailErr && (
            <div className="text-danger text-sm" role="alert">
              {emailErr}
            </div>
          )}
          <button
            type="submit"
            className="btn-primary btn-sm self-start"
            disabled={addMember.isPending}
          >
            {addMember.isPending ? "Adding…" : "Add to team"}
          </button>
        </form>
      )}

      {showLink && linkData && (
        <div className="surface p-3 flex flex-col gap-2">
          <div className="label">Share this link</div>
          <input
            readOnly
            className="input font-mono text-xs"
            value={linkData.url}
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="flex items-center justify-between gap-2">
            <button type="button" className="btn-secondary btn-sm" onClick={copyLink}>
              Copy
            </button>
            <span className="text-faint text-xs">
              Expires {new Date(linkData.expires_at).toLocaleDateString()}
            </span>
          </div>
          <p className="text-faint text-xs">
            Recipients click the link → sign up (or sign in) → join the team
            automatically. No email is sent; you share it however you want.
          </p>
        </div>
      )}
    </div>
  );
}
