// Team + Project + Goal + Milestone + Task queries.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type Team = {
  id: string;
  name: string;
  description?: string;
  archived: boolean;
  created_at: string;
  role?: "leader" | "member";
};

export type Project = {
  id: string;
  team_id: string;
  kind: "general" | "paper";
  name: string;
  description?: string;
  finalized_at?: string | null;
  finalized_by?: string | null;
  participant_user_ids: string[];
  contrib_visibility: "leader_only" | "members";
  target_venue?: string | null;
  venue_kind?: string | null;
  submission_deadline?: string | null;
};

export type Goal = {
  id: string;
  project_id: string;
  title: string;
  description?: string;
  target_date?: string | null;
  progress_pct: number;
};

export type Milestone = {
  id: string;
  goal_id: string;
  title: string;
  due_date?: string | null;
  completed_at?: string | null;
};

export type Task = {
  id: string;
  milestone_id: string;
  assignee_user_id: string;
  category_code: string;
  title: string;
  description?: string | null;
  weight: number;
  est_hours: number;
  start_date: string;
  due_date: string;
  status: "proposed" | "todo" | "in_progress" | "in_review" | "needs_rework" | "done";
  points_awarded?: string | null;
  first_submitted_at?: string | null;
  accepted_at?: string | null;
  proposed: boolean;
  split_from_task_id?: string | null;
  proposer_user_id?: string | null;
};

export function useTeams() {
  return useQuery({
    queryKey: ["teams"],
    queryFn: () => api<Team[]>("/teams"),
  });
}

export function useTeam(teamId: string | undefined) {
  return useQuery({
    queryKey: ["team", teamId],
    enabled: Boolean(teamId),
    queryFn: () => api<Team>(`/teams/${teamId}`),
  });
}

export function useCreateTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      api<Team>("/teams", { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });
}

export function useTeamProjects(teamId: string | undefined) {
  return useQuery({
    queryKey: ["team-projects", teamId],
    enabled: Boolean(teamId),
    queryFn: () => api<Project[]>(`/teams/${teamId}/projects`),
  });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: ["project", projectId],
    enabled: Boolean(projectId),
    queryFn: () => api<Project>(`/projects/${projectId}`),
  });
}

export function useCreateProject(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Project> & { kind: "general" | "paper"; name: string; participant_user_ids: string[] }) =>
      api<Project>(`/teams/${teamId}/projects`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team-projects", teamId] }),
  });
}

export function useProjectGoals(projectId: string | undefined) {
  return useQuery({
    queryKey: ["project-goals", projectId],
    enabled: Boolean(projectId),
    queryFn: () => api<Goal[]>(`/projects/${projectId}/goals`),
  });
}

export function useCreateGoal(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description?: string; target_date?: string }) =>
      api<Goal>("/goals", { method: "POST", json: { ...body, project_id: projectId } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project-goals", projectId] }),
  });
}

export function useGoalMilestones(goalId: string | undefined) {
  return useQuery({
    queryKey: ["goal-milestones", goalId],
    enabled: Boolean(goalId),
    queryFn: () => api<Milestone[]>(`/goals/${goalId}/milestones`),
  });
}

export function useCreateMilestone(goalId: string, projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; due_date?: string }) =>
      api<Milestone>(`/goals/${goalId}/milestones`, { method: "POST", json: body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["goal-milestones", goalId] });
      qc.invalidateQueries({ queryKey: ["project-goals", projectId] });
    },
  });
}

export function useToggleMilestone(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; complete: boolean }) =>
      api<Milestone>(`/milestones/${vars.id}`, { method: "PATCH", json: { complete: vars.complete } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", projectId] }),
  });
}

export function useMilestoneTasks(milestoneId: string | undefined) {
  return useQuery({
    queryKey: ["milestone-tasks", milestoneId],
    enabled: Boolean(milestoneId),
    queryFn: () => api<Task[]>(`/milestones/${milestoneId}/tasks`),
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      milestone_id: string;
      assignee_user_id: string;
      title: string;
      description?: string;
      category_code: string;
      weight: number;
      est_hours: number;
      start_date: string;
      due_date: string;
    }) => api<Task>("/tasks", { method: "POST", json: body }),
    onSuccess: (_, vars) =>
      qc.invalidateQueries({ queryKey: ["milestone-tasks", vars.milestone_id] }),
  });
}

export function useSubmitTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; note?: string }) =>
      api<Task>(`/tasks/${vars.id}/submit`, { method: "POST", json: { note: vars.note ?? "" } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["milestone-tasks"] }),
  });
}

export function useReviewTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; decision: "accept" | "reject"; quality: number; note?: string }) =>
      api<Task>(`/tasks/${vars.id}/review`, {
        method: "POST",
        json: { decision: vars.decision, quality: vars.quality, note: vars.note },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["milestone-tasks"] }),
  });
}

export function useInviteMember(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role?: "leader" | "member" }) =>
      api(`/teams/${teamId}/invitations`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team", teamId] }),
  });
}

export function useAcceptInvite() {
  return useMutation({
    mutationFn: (token: string) => api(`/invitations/${token}/accept`, { method: "POST" }),
  });
}
