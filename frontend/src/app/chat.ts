// Team chat: REST history + live WebSocket, with @mention parsing.
//
// The socket is same-origin by default (Vite dev proxy / mono-host deploy), so
// the HttpOnly `tl_access` cookie authenticates the upgrade. On a split deploy
// the Vercel rewrite does not proxy WebSockets, so the hook degrades to REST
// sends plus polling rather than silently failing.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, buildUrl } from "./api";

export type ChatMessage = {
  id: string;
  team_id: string;
  sender_user_id: string;
  seq: number;
  body: string;
  mentions: string[];
  edited_at?: string | null;
  deleted: boolean;
  created_at: string;
};

export type ChatStatus = "connecting" | "live" | "polling" | "offline";

const POLL_MS = 30_000;
const HISTORY_LIMIT = 50;

/** ws(s):// URL for an API path, derived from the configured API base. */
export function wsUrlFor(path: string): string {
  const url = buildUrl(path);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function merge(existing: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const byId = new Map(existing.map((m) => [m.id, m]));
  for (const m of incoming) byId.set(m.id, { ...byId.get(m.id), ...m });
  return [...byId.values()].sort((a, b) => a.seq - b.seq);
}

export type TeamChat = {
  messages: ChatMessage[];
  status: ChatStatus;
  unread: number;
  send: (body: string) => Promise<void>;
  markRead: () => void;
  error: string | null;
};

export function useTeamChat(teamId: string | undefined, meId: string | undefined): TeamChat {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>("connecting");
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const lastSeqRef = useRef(0);

  // --- history (always; also the polling fallback) -------------------------
  const loadHistory = useCallback(
    async (quiet = false) => {
      if (!teamId) return;
      if (!quiet) setStatus((s) => (s === "live" ? s : "connecting"));
      try {
        const rows = await api<ChatMessage[]>(`/teams/${teamId}/messages`, {
          params: { limit: HISTORY_LIMIT },
        });
        setMessages((prev) => (prev.length ? merge(prev, rows) : rows));
        lastSeqRef.current = rows.reduce((m, r) => Math.max(m, r.seq), 0);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load messages");
        setStatus("offline");
      }
    },
    [teamId],
  );

  useEffect(() => {
    setMessages([]);
    setUnread(0);
    lastSeqRef.current = 0;
    void loadHistory();
  }, [loadHistory]);

  // --- live socket ---------------------------------------------------------
  useEffect(() => {
    if (!teamId) return;
    let disposed = false;
    let timer: number | undefined;
    let ws: WebSocket | null = null;

    const connect = () => {
      if (disposed) return;
      let socket: WebSocket;
      try {
        socket = new WebSocket(wsUrlFor(`/teams/${teamId}/chat`));
      } catch {
        setStatus("polling");
        return;
      }
      ws = socket;
      socketRef.current = socket;

      socket.onopen = () => {
        retryRef.current = 0;
        setStatus("live");
        setError(null);
      };
      socket.onmessage = (ev: MessageEvent<string>) => {
        let frame: Record<string, unknown>;
        try {
          frame = JSON.parse(ev.data) as Record<string, unknown>;
        } catch {
          return;
        }
        if (frame.type === "sync" && Array.isArray(frame.messages)) {
          const rows = frame.messages as ChatMessage[];
          setMessages((prev) => merge(prev, rows));
          lastSeqRef.current = rows.reduce((m, r) => Math.max(m, r.seq), 0);
          return;
        }
        if (frame.type === "message") {
          const msg = frame as unknown as ChatMessage;
          setMessages((prev) => merge(prev, [msg]));
          lastSeqRef.current = Math.max(lastSeqRef.current, msg.seq);
          if (meId && msg.sender_user_id !== meId) setUnread((n) => n + 1);
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        socketRef.current = null;
        setStatus("polling");
        const attempt = (retryRef.current += 1);
        const delay = Math.min(1000 * 2 ** (attempt - 1), 15_000);
        timer = window.setTimeout(connect, delay);
      };
      socket.onerror = () => setStatus("polling");
    };

    connect();
    return () => {
      disposed = true;
      if (timer) window.clearTimeout(timer);
      socketRef.current = null;
      ws?.close();
    };
  }, [teamId, meId]);

  // --- polling while the socket is not live --------------------------------
  useEffect(() => {
    if (status === "live") return;
    const t = window.setInterval(() => void loadHistory(true), POLL_MS);
    return () => window.clearInterval(t);
  }, [status, loadHistory]);

  const send = useCallback(
    async (body: string) => {
      const text = body.trim();
      if (!teamId || !text) return;
      const socket = socketRef.current;
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(
          JSON.stringify({ type: "send", body: text, client_msg_id: crypto.randomUUID() }),
        );
        return;
      }
      // Socket unavailable (split deploy or reconnecting) — REST still works.
      const created = await api<ChatMessage>(`/teams/${teamId}/messages`, {
        method: "POST",
        json: { body: text },
      });
      setMessages((prev) => merge(prev, [created]));
    },
    [teamId],
  );

  const markRead = useCallback(() => {
    setUnread(0);
    if (!teamId || !lastSeqRef.current) return;
    void api(`/teams/${teamId}/read`, {
      method: "POST",
      params: { seq: lastSeqRef.current },
    }).catch(() => undefined);
  }, [teamId]);

  return { messages, status, unread, send, markRead, error };
}

// ---------------------------------------------------------------------------
// @mention helpers (shared by the composer and the renderer)
// ---------------------------------------------------------------------------

/** Detects a trailing "@partial" at the caret. */
export function mentionQueryAt(
  text: string,
  caret: number,
): { query: string; start: number } | null {
  // Names may contain spaces ("Ada Lovelace") and the composer shows
  // suggestions as soon as "@" is typed, so allow a trailing space too.
  const match = /(^|\s)@([A-Za-z0-9_.-]*(?:[ ][A-Za-z0-9_.-]+)*[ ]?)$/.exec(
    text.slice(0, caret),
  );
  if (!match) return null;
  const query = match[2] ?? "";
  return { query, start: caret - query.length - 1 };
}

/** Splits a body into plain / @mention segments for highlighting. */
export function splitMentions(
  body: string,
  names: string[],
): Array<{ text: string; mention: boolean }> {
  const escaped = names
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!escaped.length) return [{ text: body, mention: false }];
  const re = new RegExp(`@(${escaped.join("|")})\\b`, "gi");
  const out: Array<{ text: string; mention: boolean }> = [];
  let last = 0;
  for (const m of body.matchAll(re)) {
    const start = m.index ?? 0;
    if (start > last) out.push({ text: body.slice(last, start), mention: false });
    out.push({ text: m[0], mention: true });
    last = start + m[0].length;
  }
  if (last < body.length) out.push({ text: body.slice(last), mention: false });
  return out;
}

/** Members matching a mention prefix, excluding the current user. */
export function filterMembers<T extends { user_id: string; display_name: string }>(
  members: T[],
  query: string,
  meId?: string,
): T[] {
  const q = query.toLowerCase();
  return members
    .filter((m) => (meId ? m.user_id !== meId : true))
    .filter((m) => m.display_name.toLowerCase().includes(q))
    .slice(0, 6);
}
