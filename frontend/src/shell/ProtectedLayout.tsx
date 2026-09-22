import { Navigate, Outlet } from "react-router-dom";
import { useMe } from "../app/auth";
import Layout from "./Layout";

export default function ProtectedLayout() {
  const me = useMe();
  if (me.isLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center text-ink-muted">
        <div className="flex items-center gap-2">
          <span className="inline-block w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          Loading…
        </div>
      </main>
    );
  }
  if (!me.data) {
    return <Navigate to="/login" replace />;
  }
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}
