// Notifications page + unread count badge.
import { api } from "../app/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Card, Button, ErrorBox } from "../components/ui";

type Notification = {
  id: string;
  kind: string;
  payload: unknown;
  read_at: string | null;
  created_at: string;
};

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<Notification[]>("/notifications"),
    refetchInterval: 15_000,
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api<{ unread: number }>("/notifications/unread-count"),
    refetchInterval: 15_000,
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api("/notifications/read-all", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export default function NotificationsPage() {
  const list = useNotifications();
  const markAll = useMarkAllRead();
  const [error] = useState<string | null>(null);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Notifications</h1>
        <Button onClick={() => markAll.mutate()} disabled={markAll.isPending}>
          Mark all read
        </Button>
      </div>
      <ErrorBox message={error ?? undefined} />
      <Card>
        {list.isLoading ? (
          <div className="text-slate-500">Loading…</div>
        ) : list.data && list.data.length > 0 ? (
          <ul className="flex flex-col gap-2 text-sm">
            {list.data.map((n) => (
              <li
                key={n.id}
                className={`border-b pb-2 ${n.read_at ? "text-slate-500" : "text-ink"}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{n.kind}</span>
                  <span className="text-xs text-slate-400">
                    {new Date(n.created_at).toLocaleString()}
                  </span>
                </div>
                <pre className="text-xs text-slate-600 overflow-x-auto">
                  {JSON.stringify(n.payload, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-slate-500">No notifications.</div>
        )}
      </Card>
    </div>
  );
}
