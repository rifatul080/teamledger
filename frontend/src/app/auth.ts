// Centralized auth state + queries. HttpOnly cookies drive session; me() is the source of truth.
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type Me = {
  id: string;
  email: string;
  display_name: string;
  timezone: string;
  created_at: string;
};

export function useMe(enabled = true) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/me"),
    enabled,
    retry: false,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api("/auth/login", { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api("/auth/logout", { method: "POST" }),
    onSuccess: () => qc.clear(),
  });
}

export function useSignup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string; display_name: string; timezone?: string }) =>
      api("/auth/signup", { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries(),
  });
}
