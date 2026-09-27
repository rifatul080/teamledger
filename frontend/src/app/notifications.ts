import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type ActivityKind =
  | "mention"
  | "thread_reply"
  | "reaction"
  | "task_assigned"
  | "task_reviewed"
  | "milestone"
  | "member"
  | "system";

export type ActivityItem = {
  id: string;
  kind: ActivityKind;
  team_id?: string;
  project_id?: string;
  task_id?: string;
  message_id?: string;
  thread_root_id?: string;
  actor_user_id?: string;
  actor_name?: string;
  actor_avatar?: string | null;
  body: string;
  href?: string;
  read: boolean;
  created_at: string;
};

export function useActivity(teamId?: string) {
  return useQuery({
    queryKey: ["activity", teamId ?? "all"],
    enabled: true,
    queryFn: () =>
      api<{
        items: ActivityItem[];
        unread: number;
        by_kind: Record<ActivityKind, number>;
      }>(teamId ? `/teams/${teamId}/activity` : `/activity`),
    refetchInterval: 30_000,
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ["activity", "unread-count"],
    queryFn: () =>
      api<{ unread: number; by_kind: Record<ActivityKind, number> }>(
        `/activity/unread-count`,
      ),
    refetchInterval: 30_000,
  });
}

export function useMarkActivityRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { ids?: string[]; all?: boolean; kind?: ActivityKind }) =>
      api("/activity/read", { method: "POST", json: vars }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["activity"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

// ---------------------------------------------------------------------------
// The durable notification rows (assignment, mention, deadline reminders).
// The activity feed above is derived from the audit log; these are the records
// that carry a read flag, so the app bar and the sidebar badge agree.
// ---------------------------------------------------------------------------

export type NotificationRow = {
  id: string;
  type: string;
  title: string;
  body: string;
  team_id?: string | null;
  project_id?: string | null;
  task_id?: string | null;
  read: boolean;
  created_at: string;
};

export function useNotifications(limit = 10) {
  return useQuery({
    queryKey: ["notifications", limit],
    queryFn: () => api<NotificationRow[]>("/notifications", { params: { limit } }),
    refetchInterval: 20_000,
  });
}

export function useMarkNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids?: string[]) =>
      ids?.length
        ? api("/notifications/read", { method: "POST", json: { ids } })
        : api("/notifications/read-all", { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}
