// Centralized auth state + queries. HttpOnly cookies drive session; me() is the source of truth.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

export type Me = {
  id: string;
  email: string;
  display_name: string;
  timezone: string;
  avatar_url?: string | null;
  email_verified?: boolean;
  theme?: "light" | "dark" | null;
  institution?: string | null;
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
    mutationFn: (body: {
      email: string;
      password: string;
      display_name: string;
      timezone?: string;
      institution?: string;
    }) => api("/auth/signup", { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: (token: string) => api("/auth/verify-email", { method: "POST", json: { token } }),
  });
}

export function useResendVerification() {
  return useMutation({
    mutationFn: () => api("/auth/resend-verification", { method: "POST" }),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      display_name?: string;
      timezone?: string;
      theme?: "light" | "dark";
      institution?: string;
    }) => api<Me>("/me", { method: "PATCH", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useUploadAvatar() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api<{ avatar_url: string }>("/me/avatar", {
        method: "POST",
        body: fd,
        raw: true,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}
