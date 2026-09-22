import { Link } from "react-router-dom";
import { useTheme } from "../app/theme";

export default function LandingPage() {
  const [theme, , toggle] = useTheme();
  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-accent text-white font-semibold">
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12l3-3 3 3 4-5" />
              <circle cx="3" cy="12" r="1" fill="currentColor" />
              <circle cx="6" cy="9" r="1" fill="currentColor" />
              <circle cx="9" cy="12" r="1" fill="currentColor" />
              <circle cx="13" cy="7" r="1" fill="currentColor" />
            </svg>
          </span>
          <span className="text-h2 tracking-tight">TeamLedger</span>
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={toggle}
              aria-label="Toggle theme"
            >
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            <Link to="/login" className="btn-secondary btn-sm">
              Sign in
            </Link>
            <Link to="/signup" className="btn-primary btn-sm">
              Get started
            </Link>
          </div>
        </div>
      </header>
      <main>
        <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-ink leading-tight">
            A research team tool that takes authorship seriously.
          </h1>
          <p className="mt-6 text-lg text-ink-subtle max-w-2xl prose-readable">
            TeamLedger is a calm workspace for project teams planning a paper,
            a thesis, or grant-funded research. Plan the work, track who did
            what, and walk into submission with an evidence-based record of
            contribution — no spreadsheet archaeology, no awkward authorship
            conversation.
          </p>
          <div className="mt-8 flex gap-3">
            <Link to="/signup" className="btn-primary">
              Create your account
            </Link>
            <Link to="/login" className="btn-secondary">
              I already have one
            </Link>
          </div>
        </section>
        <section className="border-t border-line bg-paper-muted">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <Feat title="Four task views, one source of truth.">
              Board, list, calendar, and timeline all read the same data.
              Switching views never duplicates or reorders anything.
            </Feat>
            <Feat title="CRediT categories with weighted scoring.">
              Tag work with the standard 14 contributor roles. Author order is
              computed from category weights a leader can tune in real time.
            </Feat>
            <Feat title="A record you can defend.">
              Every point links to its source. Disputed scores are resolved
              before finalization. Finalized records are revisioned — never
              silently overwritten.
            </Feat>
            <Feat title="Onboarding that respects your time.">
              Pick the kind of work you do; we preset sensible categories and
              weights you can edit before saving.
            </Feat>
            <Feat title="Command palette for keyboard people.">
              Press <Kbd>Ctrl</Kbd>/<Kbd>⌘</Kbd>+<Kbd>K</Kbd> to jump to any
              team, project, task, or person — or run an action.
            </Feat>
            <Feat title="Invite-only, not surveillance.">
              Anyone can sign up; nobody can join a team without an email
              invite from a leader.
            </Feat>
          </div>
        </section>
        <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <h2 className="text-h1 mb-4">Built for one specific moment.</h2>
          <p className="text-body prose-readable">
            The hardest part of a research project isn't doing the work — it's
            the last week before submission, when someone asks "so, who's
            actually going to be on this paper?" TeamLedger replaces that
            conversation with a record the team has been building all along.
            Reviewed scores, evidence per point, and a snapshot of what was
            decided when.
          </p>
        </section>
      </main>
      <footer className="border-t border-line">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 text-meta flex items-center justify-between">
          <span>© TeamLedger</span>
          <span>Invite-only. No tracking. No ads.</span>
        </div>
      </footer>
    </div>
  );
}

function Feat({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <div className="text-h2 mb-1">{title}</div>
      <div className="text-body">{children}</div>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="font-mono text-xs px-1.5 py-0.5 rounded border border-line bg-paper-muted">
      {children}
    </kbd>
  );
}
