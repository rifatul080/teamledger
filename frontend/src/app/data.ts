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
  contrib_visibility: "leader_only" | "all";
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
  status:
    | "proposed"
    | "todo"
    | "in_progress"
    | "in_review"
    | "needs_rework"
    | "done";
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
    mutationFn: (body: {
      name: string;
      description?: string;
      work_type?: WorkType;
      category_preset?: string;
      categories?: string[];
    }) => api<Team>("/teams", { method: "POST", json: body }),
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
    mutationFn: (
      body: Partial<Project> & {
        kind: "general" | "paper";
        name: string;
        participant_user_ids: string[];
      },
    ) =>
      api<Project>(`/teams/${teamId}/projects`, { method: "POST", json: body }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["team-projects", teamId] }),
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
    mutationFn: (body: {
      title: string;
      description?: string;
      target_date?: string;
    }) =>
      api<Goal>("/goals", {
        method: "POST",
        json: { ...body, project_id: projectId },
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["project-goals", projectId] }),
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
      api<Milestone>(`/goals/${goalId}/milestones`, {
        method: "POST",
        json: body,
      }),
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
      api<Milestone>(`/milestones/${vars.id}`, {
        method: "PATCH",
        json: { complete: vars.complete },
      }),
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

export function useProjectTasks(projectId: string | undefined) {
  return useQuery({
    queryKey: ["project-tasks", projectId],
    enabled: Boolean(projectId),
    queryFn: () => api<Task[]>(`/projects/${projectId}/tasks`),
  });
}

export function useCreateTask(projectId: string | undefined) {
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["milestone-tasks"] });
      qc.invalidateQueries({ queryKey: ["project-tasks", projectId] });
    },
  });
}

export function useUpdateTaskStatus(projectId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; status: Task["status"] }) =>
      api<Task>(`/tasks/${vars.id}`, {
        method: "PATCH",
        json: { status: vars.status },
      }),
    onSuccess: (data) => {
      // Optimistic update path also calls setQueryData; this just invalidates.
      qc.invalidateQueries({ queryKey: ["milestone-tasks", data.milestone_id] });
      qc.invalidateQueries({ queryKey: ["project-tasks", projectId] });
    },
  });
}

export function useSubmitTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { id: string; note?: string }) =>
      api<Task>(`/tasks/${vars.id}/submit`, {
        method: "POST",
        json: { note: vars.note ?? "" },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["milestone-tasks"] }),
  });
}

export function useReviewTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: {
      id: string;
      decision: "accept" | "reject";
      quality: number;
      note?: string;
    }) =>
      api<Task>(`/tasks/${vars.id}/review`, {
        method: "POST",
        json: {
          decision: vars.decision,
          quality: vars.quality,
          note: vars.note,
        },
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
    mutationFn: (token: string) =>
      api(`/invitations/${token}/accept`, { method: "POST" }),
  });
}

export function useTeamMembers(teamId: string | undefined) {
  return useQuery({
    queryKey: ["team-members", teamId],
    enabled: Boolean(teamId),
    queryFn: () =>
      api<{ user_id: string; email: string; display_name: string; role: "leader" | "member"; avatar_url?: string | null }[]>(
        `/teams/${teamId}/members`,
      ),
  });
}

export function useUserDirectory() {
  return useQuery({
    queryKey: ["user-directory"],
    queryFn: () =>
      api<{ id: string; display_name: string; email: string; avatar_url?: string | null }[]>(
        "/users/directory",
      ),
  });
}

export function useSearch() {
  return useMutation({
    mutationFn: (q: string) =>
      api<{
        tasks: { id: string; title: string; project_id: string; status: string }[];
        messages: { id: string; body: string; team_id: string }[];
        files: { id: string; name: string; team_id: string }[];
      }>(`/search?q=${encodeURIComponent(q)}`),
  });
}

export function useCreditCategories() {
  return useQuery({
    queryKey: ["credit-categories"],
    queryFn: () => api<{ code: string; label: string }[]>("/credit-categories"),
    staleTime: 60 * 60 * 1000,
  });
}

// Onboarding — work types + presets
export const WORK_TYPES = [
  { value: "conference_paper", label: "Conference paper" },
  { value: "journal", label: "Journal submission" },
  { value: "thesis", label: "Thesis or dissertation" },
  { value: "lab_research", label: "Ongoing lab research" },
  { value: "grant", label: "Grant proposal" },
] as const;
export type WorkType = (typeof WORK_TYPES)[number]["value"];

export const PRESETS: Record<WorkType, { label: string; categories: { code: string; weight: number }[] }> = {
  conference_paper: {
    label: "Conference paper",
    categories: [
      { code: "software", weight: 1.5 },
      { code: "investigation", weight: 1.4 },
      { code: "methodology", weight: 1.2 },
      { code: "writing_original_draft", weight: 1.0 },
      { code: "writing_review_editing", weight: 0.8 },
      { code: "formal_analysis", weight: 1.0 },
      { code: "validation", weight: 0.8 },
    ],
  },
  journal: {
    label: "Journal submission",
    categories: [
      { code: "writing_original_draft", weight: 1.4 },
      { code: "investigation", weight: 1.2 },
      { code: "methodology", weight: 1.3 },
      { code: "formal_analysis", weight: 1.2 },
      { code: "validation", weight: 1.0 },
      { code: "writing_review_editing", weight: 1.0 },
      { code: "conceptualization", weight: 1.0 },
    ],
  },
  thesis: {
    label: "Thesis / dissertation",
    categories: [
      { code: "writing_original_draft", weight: 1.5 },
      { code: "conceptualization", weight: 1.2 },
      { code: "investigation", weight: 1.3 },
      { code: "methodology", weight: 1.2 },
      { code: "formal_analysis", weight: 1.0 },
      { code: "writing_review_editing", weight: 1.0 },
    ],
  },
  lab_research: {
    label: "Wet-lab / ongoing lab research",
    categories: [
      { code: "data_curation", weight: 1.3 },
      { code: "methodology", weight: 1.3 },
      { code: "investigation", weight: 1.4 },
      { code: "formal_analysis", weight: 1.0 },
      { code: "validation", weight: 1.0 },
      { code: "writing_original_draft", weight: 0.8 },
      { code: "project_administration", weight: 0.8 },
    ],
  },
  grant: {
    label: "Grant proposal",
    categories: [
      { code: "conceptualization", weight: 1.4 },
      { code: "funding_acquisition", weight: 1.3 },
      { code: "writing_original_draft", weight: 1.4 },
      { code: "project_administration", weight: 1.0 },
      { code: "supervision", weight: 0.8 },
    ],
  },
};
