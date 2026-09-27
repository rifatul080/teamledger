import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  NotificationRow,
  useMarkNotificationsRead,
  useNotifications,
} from "../../app/notifications";
import { pushToast } from "../ui/Toast";

const LABELS: Record<string, string> = {
  task_assigned: "Task",
  task_reviewed: "Review",
  mention: "Mention",
  milestone: "Milestone",
  member: "Team",
  system: "Update",
  deadline_3d: "Due in 3 days",
  deadline_1d: "Due tomorrow",
  overdue: "Overdue",
  assignment: "Task",
  review_result: "Review",
};

/** Where a notification row points, given what the row carries. */
function hrefFor(n: NotificationRow): string {
  if (n.project_id && n.task_id) return `/projects/${n.project_id}?task=${n.task_id}`;
  if (n.project_id) return `/projects/${n.project_id}`;
  if (n.team_id) return `/teams/${n.team_id}/chat`;
  return "/notifications";
}

/**
 * The app-wide notification bar. Shows unread items (assignments, mentions,
 * deadline reminders) and raises a toast the moment a new one lands while the
 * tab is in the foreground, so a teammate's @mention is not missed.
 */
export function NotificationBar() {
  const { data, isError } = useNotifications(10);
  const markRead = useMarkNotificationsRead();
  const loc = useLocation();
  const seenRef = useRef<string | null>(null);
  const onFeedPage = loc.pathname === "/notifications";

  const unread = (data ?? []).filter((n) => !n.read);

  useEffect(() => {
    const ids = (data ?? []).map((n) => n.id);
    if (ids.length === 0) {
      seenRef.current = null;
      return;
    }
    const known = seenRef.current;
    if (known === null) {
      // First load of the session: adopt the list without shouting about it.
      seenRef.current = ids[0] ?? null;
      return;
    }
    const fresh = (data ?? []).find((n) => n.id !== known && !n.read);
    if (fresh && document.visibilityState === "visible" && !onFeedPage) {
      pushToast({
        kind: fresh.type === "overdue" ? "warn" : "info",
        title: fresh.title,
        body: fresh.body,
        timeout: 8000,
      });
    }
    seenRef.current = ids[0] ?? null;
  }, [data, onFeedPage]);

  if (isError || unread.length === 0 || onFeedPage) return null;

  const show = unread.slice(0, 3);

  return (
    <div
      className="border-b border-line bg-paper-sun/60 px-4 sm:px-6 lg:px-8 py-2 flex items-center gap-3"
      role="status"
      aria-live="polite"
    >
      <span className="text-sm font-medium text-ink">
        {unread.length} new {unread.length === 1 ? "update" : "updates"}
      </span>
      <ul className="hidden md:flex items-center gap-2 min-w-0 flex-1">
        {show.map((n) => (
          <li key={n.id} className="min-w-0">
            <Link
              to={hrefFor(n)}
              className="text-sm text-ink-muted hover:text-accent underline decoration-line underline-offset-2 truncate inline-block max-w-[22rem]"
              title={n.body}
            >
              <span className="text-faint">{LABELS[n.type] ?? "Update"}:</span> {n.title}
            </Link>
          </li>
        ))}
        {unread.length > show.length && (
          <li className="text-faint text-sm">+{unread.length - show.length} more</li>
        )}
      </ul>
      <div className="flex items-center gap-2 ml-auto">
        <Link to="/notifications" className="btn-ghost btn-sm">
          Open activity
        </Link>
        <button
          className="btn-ghost btn-sm"
          onClick={() => markRead.mutate(undefined)}
          disabled={markRead.isPending}
        >
          Mark read
        </button>
      </div>
    </div>
  );
}
