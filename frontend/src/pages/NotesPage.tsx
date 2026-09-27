import { useState } from "react";
import { useCreateNote, useDeleteNote, useNotes, useUpdateNote, Note } from "../app/data";
import { EmptyState } from "../components/ui/EmptyState";
import { pushToast } from "../components/ui/Toast";

const BLANK = { title: "", content: "" };

export default function NotesPage() {
  const notes = useNotes();
  const create = useCreateNote();
  const update = useUpdateNote();
  const del = useDeleteNote();

  const [draft, setDraft] = useState(BLANK);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editing, setEditing] = useState(BLANK);

  const rows: Note[] = notes.data ?? [];

  async function add() {
    if (!draft.title.trim() && !draft.content.trim()) return;
    try {
      await create.mutateAsync({ title: draft.title.trim(), content: draft.content });
      setDraft(BLANK);
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Could not save note",
        body: e instanceof Error ? e.message : "Please try again.",
      });
    }
  }

  async function saveEdit(id: string) {
    try {
      await update.mutateAsync({ id, title: editing.title, content: editing.content });
      setEditingId(null);
      setEditing(BLANK);
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Could not update note",
        body: e instanceof Error ? e.message : "Please try again.",
      });
    }
  }

  async function togglePin(n: Note) {
    await update.mutateAsync({ id: n.id, pinned: !n.pinned });
  }

  async function remove(id: string) {
    await del.mutateAsync(id);
    pushToast({ kind: "ok", title: "Note deleted" });
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-h1">Notes</h1>
        <p className="text-meta">
          Private to you — links you want to keep, ideas, and things to follow up
          on. Nobody on your teams can see this.
        </p>
      </header>

      <section className="card flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="label">New note</span>
          <input
            className="input"
            placeholder="Title"
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          />
        </label>
        <textarea
          className="input min-h-[5rem]"
          placeholder="Anything you want to remember…"
          value={draft.content}
          onChange={(e) => setDraft({ ...draft, content: e.target.value })}
        />
        <button
          className="btn-primary self-start"
          onClick={() => void add()}
          disabled={create.isPending}
        >
          {create.isPending ? "Saving…" : "Add note"}
        </button>
      </section>

      {rows.length === 0 ? (
        <EmptyState
          title="No notes yet"
          body="Jot down a link or a reminder above; pinned notes stay at the top."
        />
      ) : (
        <ul className="grid sm:grid-cols-2 gap-3">
          {rows.map((n) => (
            <li key={n.id} className="card flex flex-col gap-2">
              {editingId === n.id ? (
                <>
                  <input
                    className="input"
                    value={editing.title}
                    onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                  />
                  <textarea
                    className="input min-h-[5rem]"
                    value={editing.content}
                    onChange={(e) => setEditing({ ...editing, content: e.target.value })}
                  />
                  <div className="flex gap-2">
                    <button
                      className="btn-primary btn-sm"
                      onClick={() => void saveEdit(n.id)}
                    >
                      Save
                    </button>
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() => setEditingId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium">{n.title || "Untitled"}</span>
                    {n.pinned && <span className="text-faint text-xs">pinned</span>}
                  </div>
                  <p className="text-sm whitespace-pre-wrap">{n.content}</p>
                  <div className="text-faint text-xs">
                    {new Date(n.created_at).toLocaleString()}
                  </div>
                  <div className="flex flex-wrap gap-2 pt-1 border-t border-line">
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() => {
                        setEditingId(n.id);
                        setEditing({ title: n.title, content: n.content });
                      }}
                    >
                      Edit
                    </button>
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() => void togglePin(n)}
                    >
                      {n.pinned ? "Unpin" : "Pin"}
                    </button>
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() => void remove(n.id)}
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
