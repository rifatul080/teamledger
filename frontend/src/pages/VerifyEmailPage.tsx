import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMe, useResendVerification, useVerifyEmail } from "../app/auth";
import { pushToast } from "../components/ui/Toast";

export default function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const verify = useVerifyEmail();
  const resend = useResendVerification();
  const me = useMe();
  const [status, setStatus] = useState<"pending" | "ok" | "error">("pending");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    if (!me.data) return;
    let cancelled = false;
    (async () => {
      try {
        await verify.mutateAsync(token);
        if (!cancelled) {
          setStatus("ok");
          pushToast({ kind: "ok", title: "Email verified", body: "Welcome to TeamLedger." });
        }
      } catch (e) {
        if (!cancelled) {
          setStatus("error");
          setErr((e as { message?: string }).message ?? "Verification failed.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, me.data?.id]);

  if (!token && me.data && !me.data.email_verified) {
    return (
      <div className="max-w-md mx-auto card">
        <h1 className="text-h1 mb-2">Verify your email</h1>
        <p className="text-body mb-4">
          We sent a verification link to <strong>{me.data.email}</strong>.
          Open it to continue.
        </p>
        <button
          className="btn-secondary"
          onClick={async () => {
            try {
              await resend.mutateAsync();
              pushToast({ kind: "ok", title: "Verification email re-sent" });
            } catch (e) {
              pushToast({
                kind: "error",
                title: "Couldn't resend",
                body: (e as { message?: string }).message,
              });
            }
          }}
        >
          Resend verification email
        </button>
      </div>
    );
  }

  if (!me.data) {
    return (
      <div className="max-w-md mx-auto card">
        <h1 className="text-h1 mb-2">Verify your email</h1>
        <p className="text-body mb-4">
          We need you to <Link to="/login" className="underline">sign in</Link>{" "}
          first, then we'll complete verification.
        </p>
      </div>
    );
  }

  if (status === "ok") {
    return (
      <div className="max-w-md mx-auto card">
        <h1 className="text-h1 mb-2">Verified.</h1>
        <p className="text-body mb-4">Your email is verified. You can continue to your dashboard.</p>
        <Link to="/dashboard" className="btn-primary">
          Go to dashboard
        </Link>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="max-w-md mx-auto card">
        <h1 className="text-h1 mb-2">Verification failed</h1>
        <p className="text-body">{err}</p>
        <Link to="/dashboard" className="btn-secondary mt-4">
          Back to dashboard
        </Link>
      </div>
    );
  }
  return (
    <div className="max-w-md mx-auto card">
      <p className="text-meta">Verifying…</p>
    </div>
  );
}
