// Top-level layout + sidebar navigation.
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useLogout, useMe } from "../app/auth";
import { UnreadBadge } from "../App";

export default function Layout() {
  const me = useMe();
  const logout = useLogout();
  const nav = useNavigate();

  if (me.isLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center text-slate-600">
        Loading…
      </main>
    );
  }
  if (me.isError || !me.data) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <Link to="/login" className="text-blue-700 underline">
          Sign in
        </Link>
      </main>
    );
  }

  return (
    <div className="min-h-screen flex">
      <aside className="w-60 border-r bg-white p-4 flex flex-col">
        <Link to="/teams" className="text-lg font-semibold mb-6">
          TeamLedger
        </Link>
        <nav className="flex flex-col gap-1 text-sm">
          <SideLink to="/teams" label="Teams" />
          <SideLink to="/notifications" label={<span>Notifications <UnreadBadge /></span>} />
          <SideLink to="/profile" label="Profile" />
        </nav>
        <div className="mt-auto pt-6 text-xs text-slate-500">
          <div className="font-medium text-slate-700">{me.data.display_name}</div>
          <div>{me.data.email}</div>
          <button
            type="button"
            className="mt-2 text-blue-700 underline"
            onClick={async () => {
              await logout.mutateAsync();
              nav("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 p-6 max-w-5xl">
        <Outlet />
      </main>
    </div>
  );
}

function SideLink({ to, label }: { to: string; label: ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `px-2 py-1 rounded ${isActive ? "bg-slate-100 text-ink" : "text-slate-600 hover:text-ink"}`
      }
    >
      {label}
    </NavLink>
  );
}
