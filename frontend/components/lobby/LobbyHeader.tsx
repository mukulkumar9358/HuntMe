"use client";

import { useState } from "react";

import { secondaryButton } from "@/components/common/buttons";
import { useNewInvite } from "@/hooks/useRooms";
import { formatDuration, inviteStore, inviteUrl } from "@/lib/lobby";
import type { RoomDetail } from "@/types/api";

async function copy(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function LobbyHeader({ room, viewerIsHost, connected }: { room: RoomDetail; viewerIsHost: boolean; connected: boolean }) {
  const [note, setNote] = useState<string | null>(null);
  const newInvite = useNewInvite(room.id);

  const flash = (msg: string) => {
    setNote(msg);
    window.setTimeout(() => setNote(null), 2500);
  };

  const copyCode = async () => flash((await copy(room.room_code)) ? "Room code copied." : "Couldn't copy. Select the code and copy it manually.");

  const copyInvite = async () => {
    // Tokens are stored hashed server-side, so the link is only recoverable if this tab created it.
    // Otherwise make a fresh one (which revokes the previous link).
    let token = inviteStore.get(room.id);
    if (!token) {
      try {
        token = (await newInvite.mutateAsync()).invite_token;
        inviteStore.set(room.id, token);
      } catch {
        return flash("Couldn't create an invite link. Try again.");
      }
    }
    flash((await copy(inviteUrl(window.location.origin, token))) ? "Invite link copied." : "Couldn't copy the link.");
  };

  const settings: [string, string][] = [
    ["Hiding time", formatDuration(room.hide_duration_seconds)],
    ["Hunting time", formatDuration(room.hunt_duration_seconds)],
    ["Clues every", formatDuration(room.clue_interval_seconds)],
    ["Shrinking zone", room.shrinking_zone_enabled ? "On" : "Off"],
    ["Joining", room.join_policy === "CODE" ? "Room code" : "Invite link only"],
    ["Teams", room.auto_balance_teams ? "Balanced automatically" : "Host assigns"],
  ];

  return (
    <header>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl font-bold tracking-tight">{room.room_name}</h1>
          <p className="mt-1 text-muted">
            {room.member_count}/{room.max_players} players
            <span className="mx-2" aria-hidden="true">·</span>
            <span role="status" className={connected ? "text-green" : "text-amber"}>
              {connected ? "Live" : "Reconnecting…"}
            </span>
          </p>
        </div>
        <div className="rounded-xl border border-line bg-panel px-5 py-3">
          <p className="text-sm text-muted">Room code</p>
          <p className="font-display text-3xl font-bold tracking-[0.18em]" aria-label={`Room code ${room.room_code.split("").join(" ")}`}>
            {room.room_code}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" className={`${secondaryButton} !px-3 !py-1.5 !text-sm`} onClick={copyCode}>
              Copy code
            </button>
            {viewerIsHost && (
              <button type="button" className={`${secondaryButton} !px-3 !py-1.5 !text-sm`} onClick={copyInvite} disabled={newInvite.isPending}>
                Copy invite link
              </button>
            )}
          </div>
        </div>
      </div>
      <p role="status" className="mt-2 h-5 text-sm text-blue-soft">
        {note}
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-3">
        {settings.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3 border-b border-line pb-1.5">
            <dt className="text-muted">{k}</dt>
            <dd className="font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
    </header>
  );
}
