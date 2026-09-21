// Scoring + author order types + queries.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type ScoreRead = {
  project_id: string;
  formula_version: string;
  total_points: string;
  participants: ParticipantScore[];
  suggested_order: OrderPosition[];
  final_order: OrderPosition[] | null;
};

export type ParticipantScore = {
  user_id: string;
  display_name: string;
  total_points: string;
  share_pct: string;
  by_category: Record<string, string>;
  tasks: TaskScore[];
  adjustments: AdjustmentSummary[];
};

export type TaskScore = {
  task_id: string;
  assignee_user_id: string;
  category_code: string;
  weight: number;
  quality: number;
  days_late: number | null;
  timeliness: string;
  category_multiplier: string;
  points: string;
};

export type AdjustmentSummary = {
  delta: string;
  reason: string;
  author_user_id: string;
  created_at: string;
};

export type OrderPosition = {
  position: number;
  user_id: string;
  suggested: boolean;
  note: string | null;
};

export type SnapshotSummary = {
  id: string;
  sha256: string;
  finalized_at: string;
  finalized_by: string;
};

export function useProjectScore(projectId: string | undefined) {
  return useQuery({
    queryKey: ["project-score", projectId],
    enabled: Boolean(projectId),
    queryFn: () => api<ScoreRead>(`/projects/${projectId}/score`),
  });
}

export function useFinalizeOrder(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (positions: { position: number; user_id: string; note?: string }[]) =>
      api(`/projects/${projectId}/author-order/finalize`, {
        method: "POST",
        json: { positions },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project-score", projectId] });
      qc.invalidateQueries({ queryKey: ["project-snapshots", projectId] });
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

export function useSnapshots(projectId: string | undefined) {
  return useQuery({
    queryKey: ["project-snapshots", projectId],
    enabled: Boolean(projectId),
    queryFn: () =>
      api<SnapshotSummary[]>(`/projects/${projectId}/author-order/snapshots`),
  });
}
