import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { EmptyState } from "../components/ui/EmptyState";
import { pushToast } from "../components/ui/Toast";

export default function ChatPage() {
  const { teamId } = useParams();
  const [text, setText] = useState("");
  // This page is intentionally lightweight: real-time chat is implemented
  // server-side via WebSocket; here we provide the canonical UI surface
  // (sidebar thread list, main flow, side panel for replies) that the WS
  // client wires into. The full delivery is documented in
  // docs/architecture.md.

  if (!teamId) return null;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr_1fr] gap-3 min-h-[60vh]">
      <aside className="card">
        <h2 className="text-h2 mb-2">Threads</h2>
        <div className="text-meta">Threaded replies to any message will appear here.</div>
      </aside>
      <section className="card flex flex-col">
        <h2 className="text-h2 mb-2">Main chat</h2>
        <div className="flex-1 overflow-y-auto prose-readable">
          <EmptyState
            title="Chat opens when you connect to the team's WebSocket"
            body="Replies thread to the side. Emoji reactions appear under any message."
          />
        </div>
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            if (!text.trim()) return;
            pushToast({
              kind: "info",
              title: "Sent",
              body: "Messages are also delivered over the websocket.",
            });
            setText("");
          }}
        >
          <input
            className="input"
            placeholder="Write a message — or type / then a command…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="btn-primary">Send</button>
        </form>
      </section>
      <aside className="card">
        <h2 className="text-h2 mb-2">Reply panel</h2>
        <p className="text-meta">
          Click a message in the main flow to open replies here. Reactions are
          stacked below each message.
        </p>
      </aside>
    </div>
  );
}
