import React from "react";

const ICON: Record<string, React.ReactNode> = {
  todo: (
    <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="8" cy="8" r="6" />
    </svg>
  ),
  in_progress: (
    <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="1.6">
      <circle cx="8" cy="8" r="6" strokeDasharray="28" strokeDashoffset="14" strokeLinecap="round" />
    </svg>
  ),
  in_review: (
    <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M2 8c2-3 4-4 6-4s4 1 6 4c-2 3-4 4-6 4s-4-1-6-4z" />
      <circle cx="8" cy="8" r="1.6" />
    </svg>
  ),
  needs_rework: (
    <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M3 8a5 5 0 1 1 1.6 3.7" strokeLinecap="round" />
      <path d="M3 4v3.5h3.5" strokeLinecap="round" />
    </svg>
  ),
  done: (
    <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8.5l3 3 7-7" />
    </svg>
  ),
  proposed: (
    <svg viewBox="0 0 16 16" width="11" height="11" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M8 2v3M8 11v3M2 8h3M11 8h3" strokeLinecap="round" />
    </svg>
  ),
};

const LABEL: Record<string, string> = {
  todo: "To do",
  in_progress: "In progress",
  in_review: "In review",
  needs_rework: "Needs rework",
  done: "Done",
  proposed: "Proposed",
};

const KNOWN = new Set([
  "todo",
  "in_progress",
  "in_review",
  "needs_rework",
  "done",
  "proposed",
]);

export function StatusBadge({ status }: { status: string }) {
  const cls = KNOWN.has(status) ? `badge-${status}` : "badge-todo";
  return (
    <span className={cls}>
      {ICON[status] ?? ICON.todo}
      <span>{LABEL[status] ?? status}</span>
    </span>
  );
}
