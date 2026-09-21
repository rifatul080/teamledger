// Login + signup entry page.
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useLogin, useSignup, useMe } from "../app/auth";
import { Button, Card, ErrorBox, Input, Label } from "../components/ui";

export default function LoginPage() {
  const me = useMe();
  const login = useLogin();
  const signup = useSignup();
  const nav = useNavigate();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (me.data) {
    nav("/teams");
    return null;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (mode === "login") {
        await login.mutateAsync({ email, password });
      } else {
        await signup.mutateAsync({
          email,
          password,
          display_name: displayName || email.split("@")[0] || "user",
          timezone: "UTC",
        });
      }
      nav("/teams");
    } catch (err) {
      setError((err as Error).message ?? "Authentication failed.");
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-slate-50">
      <Card className="w-full max-w-sm">
        <h1 className="text-xl font-semibold mb-4">
          {mode === "login" ? "Sign in to TeamLedger" : "Create your account"}
        </h1>
        <form className="flex flex-col gap-3" onSubmit={submit}>
          {mode === "signup" && (
            <div>
              <Label htmlFor="display_name">Display name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </div>
          )}
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <ErrorBox message={error ?? undefined} />
          <Button type="submit" disabled={login.isPending || signup.isPending}>
            {mode === "login" ? "Sign in" : "Create account"}
          </Button>
          <button
            type="button"
            className="text-sm text-blue-700 underline"
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? "Need an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </form>
      </Card>
    </main>
  );
}
