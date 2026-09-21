// Chat queries + websocket hook.
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type ChatMessage = {
  id: string;
  team_id: string;
  sender_user_id: string;
  sender_display_name?: string;
  seq: number;
  body: string;
  mentions: string[];
  edited_at: string | null;
  deleted: boolean;
  created_at: string;
};

export function useMessages(teamId: string | undefined) {
  return useQuery({
    queryKey: ["messages", teamId],
    enabled: Boolean(teamId),
    queryFn: () =>
      api<ChatMessage[]>(
        `/teams/${teamId}/messages`,
      ),
  });
}

export function useSendMessage(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { body: string; attachment_version_ids?: string[] }) =>
      api<ChatMessage>(`/teams/${teamId}/messages`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", teamId] }),
  });
}

export function useEditMessage(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; body: string }) =>
      api<ChatMessage>(`/teams/${teamId}/messages/${vars.id}`, {
        method: "PATCH",
        json: { body: vars.body },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", teamId] }),
  });
}

export function useDeleteMessage(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/teams/${teamId}/messages/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["messages", teamId] }),
  });
}

export function useMarkRead(teamId: string) {
  return useMutation({
    mutationFn: (seq: number) =>
      api(`/teams/${teamId}/read`, { method: "POST", params: { seq: String(seq) } }),
  });
}

// WebSocket hook: connects to /api/v1/teams/{teamId}/chat using cookie auth.
// Browsers can’t send custom auth headers on WS, so we rely on the cookie.
export function useChatSocket(teamId: string | undefined, onMessage: (m: ChatMessage) => void) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  useEffect(() => {
    if (!teamId) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/v1/teams/${teamId}/chat`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data && data.type === "message") onMessage(data as ChatMessage);
      } catch {
        // ignore parse errors
      }
    };
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [teamId, onMessage]);
  return { connected, send: (payload: object) => wsRef.current?.send(JSON.stringify(payload)) };
}
