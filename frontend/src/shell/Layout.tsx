import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useMe, useLogout } from "../app/auth";
import { useUnreadCount } from "../app/notifications";
import { useTheme } from "../app/theme";
import { Avatar } from "../components/ui/Avatar";
import { CommandPalette, usePalette } from "./CommandPalette";

export default function Layout({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const logout = useLogout();
  const nav = useNavigate();
  const loc = useLocation();
  const unread = useUnreadCount();
  const [, , toggleTheme] = useTheme();
  const palette = usePalette();
  const [menuOpen, setMenuOpen] = useState(false);

  // Close account menu on route change.
  useEffect(() => setMenuOpen(false), [loc.pathname]);

  // Cmd/Ctrl+K opens the palette.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        palette.open();
      }
      if (e.key === "?" && (e.metaKey || e.ctrlKey)) {
        // Reserved for "show shortcuts" — already covered by palette's help view.
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [palette]);

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-[260px_1fr] bg-paper text-ink">
      <aside className="hidden lg:flex flex-col border-r border-line bg-paper-muted sticky top-0 h-screen">
        <Link to="/dashboard" className="px-5 py-4 flex items-center gap-2 border-b border-line-subtle">
          <Logo />
          <span className="text-h2 tracking-tight">TeamLedger</span>
        </Link>
        <nav className="flex-1 px-3 py-4 flex flex-col gap-1">
          <SideLink to="/dashboard" label="Dashboard" icon={<HomeIcon />} />
          <SideLink to="/teams" label="Teams" icon={<TeamIcon />} />
          <SideLink
            to="/notifications"
            label={
              <span className="flex items-center justify-between w-full">
                <span>Activity</span>
                {unread.data && unread.data.unread > 0 ? (
                  <span className="inline-flex items-center justify-center text-[10px] font-semibold bg-accent text-white rounded-full px-1.5 min-w-[1.25rem]">
                    {unread.data.unread}
                  </span>
                ) : null}
              </span>
            }
            icon={<BellIcon />}
          />
          <SideLink to="/me" label="Profile" icon={<UserIcon />} />
        </nav>
        <div className="px-3 py-3 border-t border-line-subtle">
          <button
            type="button"
            className="btn-ghost w-full justify-start"
            onClick={palette.open}
            aria-label="Open command palette"
          >
            <SearchIcon />
            <span>Quick find</span>
            <span className="ml-auto text-faint font-mono">Ctrl K</span>
          </button>
        </div>
        <div className="px-4 py-4 border-t border-line-subtle">
          <div className="flex items-center gap-2">
            <Avatar
              userId={me.data!.id}
              displayName={me.data!.display_name}
              size="md"
            />
            <div className="min-w-0">
              <div className="text-sm font-medium text-ink truncate">
                {me.data!.display_name}
              </div>
              <div className="text-faint truncate">{me.data!.email}</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex flex-col min-w-0">
        <header className="lg:hidden border-b border-line bg-paper sticky top-0 z-30 px-4 py-3 flex items-center gap-2">
          <Link to="/dashboard" className="flex items-center gap-2">
            <Logo />
            <span className="text-h2">TeamLedger</span>
          </Link>
          <button
            type="button"
            className="btn-ghost btn-sm ml-auto"
            onClick={palette.open}
            aria-label="Open command palette"
          >
            <SearchIcon />
          </button>
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="Account menu"
          >
            <Avatar userId={me.data!.id} displayName={me.data!.display_name} size="sm" />
          </button>
        </header>
        {menuOpen && (
          <div className="lg:hidden border-b border-line bg-paper px-4 py-2 flex flex-col gap-1">
            <Link to="/dashboard" className="btn-ghost justify-start">Dashboard</Link>
            <Link to="/teams" className="btn-ghost justify-start">Teams</Link>
            <Link to="/notifications" className="btn-ghost justify-start">Activity</Link>
            <Link to="/me" className="btn-ghost justify-start">Profile</Link>
            <button
              type="button"
              className="btn-ghost justify-start"
              onClick={() => {
                setMenuOpen(false);
                toggleTheme();
              }}
            >
              Toggle theme
            </button>
            <button
              type="button"
              className="btn-ghost justify-start"
              onClick={async () => {
                await logout.mutateAsync();
                nav("/login");
              }}
            >
              Sign out
            </button>
          </div>
        )}
        <main id="main" className="flex-1 min-w-0">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">{children}</div>
        </main>
      </div>

      <CommandPalette palette={palette} />
    </div>
  );
}

function SideLink({
  to,
  label,
  icon,
}: {
  to: string;
  label: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `btn justify-start ${isActive ? "bg-paper-sun text-ink border border-line" : "btn-ghost"}`
      }
    >
      {icon}
      <span className="truncate">{label}</span>
    </NavLink>
  );
}

function Logo() {
  return (
    <span className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-accent text-white font-semibold">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 12l3-3 3 3 4-5" />
        <circle cx="3" cy="12" r="1" fill="currentColor" />
        <circle cx="6" cy="9" r="1" fill="currentColor" />
        <circle cx="9" cy="12" r="1" fill="currentColor" />
        <circle cx="13" cy="7" r="1" fill="currentColor" />
      </svg>
    </span>
  );
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 7l6-5 6 5v7H2z" />
      <path d="M6 14V9h4v5" />
    </svg>
  );
}
function TeamIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="5.5" cy="6" r="2" />
      <path d="M2 13c0-2 1.5-3 3.5-3s3.5 1 3.5 3" />
      <circle cx="11" cy="5" r="1.7" />
      <path d="M9 13c0-1.5 1-2.5 2-2.5s2 .5 3 2" />
    </svg>
  );
}
function BellIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 12V8a4 4 0 1 1 8 0v4l1 1H3l1-1z" />
      <path d="M7 14a1 1 0 0 0 2 0" />
    </svg>
  );
}
function UserIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8" cy="6" r="2.4" />
      <path d="M3 14c0-2.5 2-4 5-4s5 1.5 5 4" />
    </svg>
  );
}
function SearchIcon() {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5l3 3" />
    </svg>
  );
}
