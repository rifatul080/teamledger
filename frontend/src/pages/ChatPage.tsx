// Team chat: live websocket + REST history.
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { useMe } from "../app/auth";
import { useDeleteMessage, useEditMessage, useMessages, useSendMessage, useChatSocket, type ChatMessage } from "../app/messaging";
import { Button, Card, ErrorBox, Input } from "../components/ui";

export default function ChatPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const me = useMe();
  const messages = useMessages(teamId);
  const send = useSendMessage(teamId ?? "");
  const edit = useEditMessage(teamId ?? "");
  const del = useDeleteMessage(teamId ?? "");
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Local store so new WS messages show immediately, even before query invalidation.
  const [live, setLive] = useState<ChatMessage[]>([]);
  useEffect(() => {
    setLive(messages.data ?? []);
  }, [messages.data]);
  const onWsMessage = useCallback((m: ChatMessage) => {
    setLive((prev) => (prev.some((x) => x.id === m.id) ? prev : [...prev, m]));
  }, []);
  const { connected } = useChatSocket(teamId, onWsMessage);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setError(null);
    try {
      await send.mutateAsync({ body: draft });
      setDraft("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Team chat</h1>
        <span className={`text-xs ${connected ? "text-green-700" : "text-slate-500"}`}>
          {connected ? "Live" : "Disconnected"}
        </span>
      </div>

      <Card className="min-h-[60vh] max-h-[70vh] overflow-y-auto">
        {live.length === 0 ? (
          <div className="text-slate-500">No messages yet.</div>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {live.map((m) => (
              <li key={m.id} className="border-b pb-1">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs text-slate-500">
                      {new Date(m.created_at).toLocaleString()}
                    </span>
                    {m.deleted ? (
                      <span className="italic text-slate-400 ml-2">[deleted]</span>
                    ) : (
                      <span className="ml-2">{m.body}</span>
                    )}
                  </div>
                  {me.data && m.sender_user_id === me.data.id && !m.deleted && (
                    <span className="flex gap-1">
                      <Button
                        variant="secondary"
                        onClick={async () => {
                          const body = window.prompt("Edit message", m.body);
                          if (body != null) await edit.mutateAsync({ id: m.id, body });
                        }}
                      >
                        Edit
                      </Button>
                      <Button variant="danger" onClick={() => del.mutate(m.id)}>
                        Delete
                      </Button>
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <form className="flex gap-2" onSubmit={submit}>
        <Input
          placeholder="Write a message…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <Button type="submit" disabled={send.isPending}>
          Send
        </Button>
      </form>
      <ErrorBox message={error ?? undefined} />
    </div>
  );
}
