"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/services/api";
import type { GameConfig, Permission, RoomCreateBody, RoomCreated, RoomDetail } from "@/types/api";

export const roomKey = (roomId: string) => ["room", roomId] as const;

/** Official limits and defaults come from the server; the UI never hardcodes them. */
export function useGameConfig() {
  return useQuery<GameConfig>({ queryKey: ["game-config"], queryFn: () => api<GameConfig>("/game-config"), staleTime: Infinity });
}

export function useRoom(roomId: string, socketConnected: boolean) {
  return useQuery<RoomDetail>({
    queryKey: roomKey(roomId),
    queryFn: () => api<RoomDetail>(`/rooms/${roomId}`),
    // The socket pushes change signals; poll only while it's down.
    refetchInterval: socketConnected ? false : 5000,
    retry: (count, error) => !(error instanceof ApiError && [401, 403, 404].includes(error.status)) && count < 2,
  });
}

export function useCreateRoom() {
  return useMutation({ mutationFn: (body: RoomCreateBody) => api<RoomCreated>("/rooms", { method: "POST", body }) });
}

export function useJoinRoom() {
  return useMutation({
    mutationFn: (body: { room_code?: string; invite_token?: string }) => api<RoomDetail>("/rooms/join", { method: "POST", body }),
  });
}

export function useLeaveRoom(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>(`/rooms/${roomId}/leave`, { method: "POST" }),
    onSuccess: () => qc.removeQueries({ queryKey: roomKey(roomId) }),
  });
}

export interface MyStatePatch {
  is_ready?: boolean;
  safety_acknowledged?: boolean;
  location_permission?: Permission;
  camera_permission?: Permission;
}

export function useUpdateMyState(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: MyStatePatch) => api<RoomDetail>(`/rooms/${roomId}/members/me`, { method: "PATCH", body: patch }),
    onSuccess: (room) => qc.setQueryData(roomKey(roomId), room),
  });
}

export function useAssignTeam(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { memberId: string; teamId: string }) =>
      api<RoomDetail>(`/rooms/${roomId}/members/${v.memberId}/team`, { method: "PATCH", body: { team_id: v.teamId } }),
    onSuccess: (room) => qc.setQueryData(roomKey(roomId), room),
  });
}

export function useNewInvite(roomId: string) {
  return useMutation({ mutationFn: () => api<{ invite_token: string; invite_expires_at: string }>(`/rooms/${roomId}/invite`, { method: "POST" }) });
}
