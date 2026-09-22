import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../app/api";
import { useSignup } from "../app/auth";
import { pushToast } from "../components/ui/Toast";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  );
  const [institution, setInstitution] = useState("");
  const [institutionHint, setInstitutionHint] = useState<string | null>(null);
  const [hintTouched, setHintTouched] = useState(false);
  const signup = useSignup();
  const nav = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!email || hintTouched) return;
    const ctrl = new AbortController();
    const id = setTimeout(async () => {
      try {
        const out = await api<{ hint: string | null }>(
          `/auth/institution-hint?email=${encodeURIComponent(email)}`,
          { signal: ctrl.signal },
        );
        setInstitutionHint(out.hint);
        if (out.hint && !institution) setInstitution(out.hint);
      } catch {
        /* ignore */
      }
    }, 250);
    return () => {
      ctrl.abort();
      clearTimeout(id);
    };
  }, [email, hintTouched, institution]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await signup.mutateAsync({
        email,
        password,
        display_name: displayName,
        timezone,
        institution: institution || undefined,
      });
      pushToast({
        kind: "info",
        title: "Account created",
        body: "Check your inbox (or the dev console) for the verification link.",
      });
      nav("/dashboard");
    } catch (err) {
      const msg = (err as { message?: string }).message ?? "Signup failed.";
      pushToast({ kind: "error", title: "Sign-up failed", body: msg });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center px-4 bg-paper-muted py-12">
      <div className="w-full max-w-md card shadow-sm">
        <div className="mb-4 flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-accent text-white font-semibold">
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12l3-3 3 3 4-5" />
            </svg>
          </span>
          <span className="text-h2">TeamLedger</span>
        </div>
        <h1 className="text-h1 mb-1">Create your account</h1>
        <p className="text-meta mb-4">
          Already a member?{" "}
          <Link to="/login" className="text-accent underline">
            Sign in
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
            {institutionHint && (
              <p className="text-faint mt-1">
                Detected academic domain — pre-filled institution below. Edit
                if it's wrong.
              </p>
            )}
          </div>
          <div>
            <label className="label" htmlFor="display">
              Your name
            </label>
            <input
              id="display"
              required
              autoComplete="name"
              className="input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="institution">
              Institution {institutionHint ? "(pre-filled)" : "(optional)"}
            </label>
            <input
              id="institution"
              className="input"
              value={institution}
              onChange={(e) => {
                setHintTouched(true);
                setInstitution(e.target.value);
              }}
              placeholder="e.g. MIT CSAIL, ETH Zürich, …"
            />
          </div>
          <div>
            <label className="label" htmlFor="tz">
              Timezone
            </label>
            <input
              id="tz"
              className="input"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
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
              minLength={10}
              autoComplete="new-password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <p className="text-faint mt-1">
              At least 10 characters, including a letter and a digit.
            </p>
          </div>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "Creating account…" : "Create account"}
          </button>
          <p className="text-faint text-center mt-1">
            By creating an account you agree to our values: invite-only team
            membership, evidence-based authorship, no surprises.
          </p>
        </form>
      </div>
    </main>
  );
}
