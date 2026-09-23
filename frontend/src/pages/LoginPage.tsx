import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useLogin } from "../app/auth";
import { useAcceptInvite } from "../app/data";
import { pushToast } from "../components/ui/Toast";

export default function LoginPage() {
  const [params] = useSearchParams();
  const nextPath = params.get("next") ?? "/dashboard";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();
  const acceptInvite = useAcceptInvite();
  const nav = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login.mutateAsync({ email, password });
      // If the user came in via an invite link, accept it now.
      let pendingToken: string | null = null;
      try {
        pendingToken = localStorage.getItem("pending_invite_token");
        if (pendingToken) localStorage.removeItem("pending_invite_token");
      } catch {
        /* ignore */
      }
      if (pendingToken) {
        try {
          const r = await acceptInvite.mutateAsync(pendingToken);
          nav(`/teams/${r.team_id}`);
          return;
        } catch {
          /* fall through */
        }
      }
      nav(nextPath);
    } catch (err) {
      const msg = (err as { message?: string }).message ?? "Sign-in failed.";
      pushToast({ kind: "error", title: "Sign in failed", body: msg });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center px-4 bg-paper-muted">
      <div className="w-full max-w-sm card shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-accent text-white font-semibold">
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12l3-3 3 3 4-5" />
            </svg>
          </span>
          <span className="text-h2">TeamLedger</span>
        </div>
        <h1 className="text-h1 mb-1">Sign in</h1>
        <p className="text-meta mb-4">
          Don't have an account?{" "}
          <Link to="/signup" className="text-accent underline">
            Create one
          </Link>
          .
        </p>
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <div>
            <label className="label" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
          <Link to="/" className="text-meta text-center mt-1 underline">
            Back to the public page
          </Link>
        </form>
      </div>
    </main>
  );
}
