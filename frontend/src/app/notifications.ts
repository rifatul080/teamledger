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
    },
  });
}
