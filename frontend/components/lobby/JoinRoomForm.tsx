"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { TextField } from "@/components/auth/TextField";
import { primaryButton } from "@/components/common/buttons";
import { useJoinRoom } from "@/hooks/useRooms";
import { ApiError } from "@/services/api";

export function joinErrorMessage(e: unknown): string {
  if (!(e instanceof ApiError)) return "Something went wrong. Try again.";
  switch (e.code) {
    case "room_not_found":
      return "We couldn't find that room. Check the code, or ask the host for a fresh invite link.";
    case "room_full":
      return "That room is full.";
    case "room_in_progress":
      return "That game has already started.";
    case "rate_limited":
      return "Too many attempts. Wait a minute and try again.";
    default:
      return e.message;
  }
}

export function JoinRoomForm() {
  const router = useRouter();
  const params = useSearchParams();
  const invite = params.get("invite");
  const [code, setCode] = useState(params.get("code") ?? "");
  const [error, setError] = useState<string | null>(null);
  const join = useJoinRoom();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const room = await join.mutateAsync(invite ? { invite_token: invite } : { room_code: code.trim() });
      router.push(`/lobby/${room.id}`);
    } catch (err) {
      setError(joinErrorMessage(err));
    }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      {error && (
        <p role="alert" className="rounded-lg border border-red/50 bg-red/10 px-4 py-3 text-sm">
          {error}
        </p>
      )}
      {invite ? (
        <p className="text-muted">You&apos;ve been invited to a game. Join to see the lobby and pick up your team.</p>
      ) : (
        <TextField
          label="Room code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          autoCapitalize="characters"
          autoComplete="off"
          spellCheck={false}
          maxLength={32}
          className="w-full rounded-lg border border-line bg-panel px-4 py-3 font-semibold uppercase tracking-widest text-text"
        />
      )}
      <button type="submit" className={`${primaryButton} w-full sm:w-auto`} disabled={join.isPending || (!invite && !code.trim())}>
        {join.isPending ? "Joining…" : "Join game"}
      </button>
    </form>
  );
}
