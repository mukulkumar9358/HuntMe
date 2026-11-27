"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/services/api";
import type { AuthResponse, User } from "@/types/api";

export const ME_KEY = ["me"] as const;

/** Current user, or null when signed out. */
export function useMe() {
  return useQuery<User | null>({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await api<User>("/users/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { identifier: string; password: string }) =>
      api<AuthResponse>("/auth/login", { method: "POST", body }),
    onSuccess: (data) => qc.setQueryData(ME_KEY, data.user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { username: string; email: string; password: string }) =>
      api<AuthResponse>("/auth/register", { method: "POST", body }),
    onSuccess: (data) => qc.setQueryData(ME_KEY, data.user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    onSettled: () => qc.setQueryData(ME_KEY, null),
  });
}
