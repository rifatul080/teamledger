import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMe } from "../app/auth";
import {
  ChatMessage,
  ChatStatus,
  filterMembers,
  mentionQueryAt,
  splitMentions,
  useTeamChat,
} from "../app/chat";
import { useTeamMembers } from "../app/data";
import { Avatar } from "../components/ui/Avatar";
import { EmptyState } from "../components/ui/EmptyState";
import { pushToast } from "../components/ui/Toast";

const STATUS_TEXT: Record<ChatStatus, string> = {
  connecting: "Connecting…",
  live: "Live",
  polling: "Reconnecting…",
  offline: "Offline",
};

export default function ChatPage() {
  const { teamId } = useParams();
  const me = useMe();
  const members = useTeamMembers(teamId);
  const chat = useTeamChat(teamId, me.data?.id);

  const [draft, setDraft] = useState("");
  const [caret, setCaret] = useState(0);
  const [highlight, setHighlight] = useState(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const memberList = useMemo(() => members.data ?? [], [members.data]);
  const nameById = useMemo(
    () => new Map(memberList.map((m) => [m.user_id, m.display_name])),
    [memberList],
  );
  const mentionNames = useMemo(() => memberList.map((m) => m.display_name), [memberList]);

  const mention = mentionQueryAt(draft, caret);
  const suggestions = mention ? filterMembers(memberList, mention.query, me.data?.id) : [];

  // Keep the transcript pinned to the newest message.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat.messages.length]);

  useEffect(() => {
    if (chat.unread === 0) chat.markRead();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.messages.length]);

  if (!teamId) return null;

  function insertMention(name: string) {
    if (!mention) return;
    const before = draft.slice(0, mention.start);
    const after = draft.slice(caret);
    setDraft(`${before}@${name} ${after}`);
    setCaret(before.length + name.length + 2);
    setHighlight(0);
    inputRef.current?.focus();
  }

  async function submit() {
    const body = draft.trim();
    if (!body) return;
    setDraft("");
    setCaret(0);
    try {
      await chat.send(body);
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Message not sent",
        body: e instanceof Error ? e.message : "Please try again.",
      });
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (suggestions.length) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlight((h) => (h + 1) % suggestions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlight((h) => (h - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === "Tab" || (e.key === "Enter" && !e.shiftKey)) {
        e.preventDefault();
        const picked = suggestions[highlight];
        if (picked) insertMention(picked.display_name);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setCaret(0);
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  }


  return (
    <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-4 h-[calc(100vh-9rem)]">
      <aside className="card overflow-y-auto">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-h2">Team</h2>
          <span
            className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded ${
              chat.status === "live" ? "bg-paper-sun text-ink-muted" : "bg-paper-muted text-faint"
            }`}
            title={
              chat.status === "live"
                ? "Connected over WebSocket"
                : "Falling back to REST polling"
            }
          >
            {STATUS_TEXT[chat.status]}
          </span>
        </div>
        <ul className="flex flex-col gap-1">
          {memberList.map((m) => (
            <li key={m.user_id} className="flex items-center gap-2 py-1">
              <Avatar userId={m.user_id} displayName={m.display_name} size="sm" />
              <span className="text-sm truncate">{m.display_name}</span>
              {m.user_id === me.data?.id && (
                <span className="text-[10px] text-faint uppercase font-mono">you</span>
              )}
            </li>
          ))}
        </ul>
      </aside>

      <section className="card flex flex-col min-h-0">
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <h1 className="text-h2">Chat</h1>
          <Link to={`/teams/${teamId}`} className="btn-ghost btn-sm">
            Team details
          </Link>
        </header>

        {chat.error && (
          <div className="px-4 py-2 text-meta text-accent border-b border-line">
            {chat.error}
          </div>
        )}

        <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
          {chat.messages.length === 0 ? (
            <EmptyState
              title="No messages yet"
              body="Say hello. Type @ to mention a teammate — they get an in-app notification and an email."
            />
          ) : (
            chat.messages.map((m) => (
              <MessageRow
                key={m.id}
                message={m}
                own={m.sender_user_id === me.data?.id}
                author={nameById.get(m.sender_user_id) ?? "Teammate"}
                mentionNames={mentionNames}
                myId={me.data?.id}
              />
            ))
          )}
        </div>

        {chat.unread > 0 && (
          <div className="px-4 py-1 text-meta border-t border-line">
            {chat.unread} new {chat.unread === 1 ? "message" : "messages"} while you were away
          </div>
        )}

        <div className="border-t border-line p-3 relative">
          {suggestions.length > 0 && (
            <ul className="absolute bottom-full mb-2 left-3 w-64 surface-raised shadow-md py-1 max-h-56 overflow-y-auto">
              {suggestions.map((m, i) => (
                <li key={m.user_id}>
                  <button
                    type="button"
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm ${
                      i === highlight ? "bg-paper-sun" : ""
                    }`}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      insertMention(m.display_name);
                    }}
                  >
                    <Avatar userId={m.user_id} displayName={m.display_name} size="sm" />
                    {m.display_name}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              className="input min-h-[2.5rem] max-h-40 resize-y"
              rows={1}
              placeholder="Message the team… use @ to mention someone"
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                setCaret(e.target.selectionStart ?? e.target.value.length);
                setHighlight(0);
              }}
              onKeyDown={onKeyDown}
              onBlur={() => window.setTimeout(() => setCaret(0), 120)}
            />
            <button className="btn-primary" onClick={() => void submit()}>
              Send
            </button>
          </div>
          <p className="text-faint text-xs mt-1">
            Enter sends · Shift+Enter adds a line · @ mentions notify a teammate
          </p>
        </div>
      </section>
    </div>
  );
}

function MessageRow({
  message,
  author,
  own,
  mentionNames,
  myId,
}: {
  message: ChatMessage;
  author: string;
  own: boolean;
  mentionNames: string[];
  myId?: string;
}) {
  const segments = useMemo(
    () => (message.deleted ? [] : splitMentions(message.body, mentionNames)),
    [message.deleted, message.body, mentionNames],
  );
  const mentionsMe = Boolean(myId && message.mentions?.includes(myId));

  return (
    <article
      className={`flex gap-2 ${own ? "flex-row-reverse" : ""} ${
        mentionsMe ? "rounded-lg bg-paper-sun/40 px-2 py-1" : ""
      }`}
    >
      <Avatar userId={message.sender_user_id} displayName={author} size="sm" />
      <div className={`min-w-0 ${own ? "text-right" : ""}`}>
        <div className="text-xs text-faint">
          <span className="font-medium text-ink-muted">{author}</span>{" "}
          {new Date(message.created_at).toLocaleString()}
        </div>
        <div className="inline-block text-sm whitespace-pre-wrap break-words text-ink">
          {message.deleted ? (
            <em className="text-faint">message deleted</em>
          ) : (
            segments.map((s, i) => (
              <span key={i} className={s.mention ? "text-accent font-medium" : undefined}>
                {s.text}
              </span>
            ))
          )}
        </div>
      </div>
    </article>
  );
}