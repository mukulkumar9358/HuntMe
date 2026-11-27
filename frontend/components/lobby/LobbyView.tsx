"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { secondaryButton } from "@/components/common/buttons";
import { LobbyHeader } from "@/components/lobby/LobbyHeader";
import { MyControls } from "@/components/lobby/MyControls";
import { PlayerRow } from "@/components/lobby/PlayerRow";
import { StartPanel } from "@/components/lobby/StartPanel";
import { TeamCard } from "@/components/lobby/TeamCard";
import { useLobbySocket } from "@/hooks/useLobbySocket";
import { useAssignTeam, useLeaveRoom, useRoom } from "@/hooks/useRooms";
import { useMe } from "@/hooks/useAuth";
import { groupByTeam } from "@/lib/lobby";
import { ApiError } from "@/services/api";

export function LobbyView({ roomId }: { roomId: string }) {
  const router = useRouter();
  const { data: user } = useMe();
  const { connected } = useLobbySocket(roomId);
  const { data: room, error, isPending } = useRoom(roomId, connected);
  const assign = useAssignTeam(roomId);
  const leave = useLeaveRoom(roomId);
  const [actionError, setActionError] = useState<string | null>(null);

  if (isPending) return <p className="mx-auto max-w-6xl px-5 py-16 text-muted sm:px-8">Loading lobby…</p>;

  if (error || !room) {
    const gone = error instanceof ApiError && [403, 404].includes(error.status);
    return (
      <div className="mx-auto max-w-xl px-5 py-16 sm:px-8">
        <h1 className="font-display text-3xl font-bold">{gone ? "You're not in this room" : "Couldn't load the lobby"}</h1>
        <p className="mt-3 text-muted">
          {gone ? "It may have closed, or you may have left. You can create a new game or join with a code." : "Check your connection and try again."}
        </p>
        <Link href="/" className={`${secondaryButton} mt-6`}>
          Back to home
        </Link>
      </div>
    );
  }

  const me = room.members.find((m) => m.id === room.me);
  const viewerIsHost = !!user && room.host_user_id === user.id;
  const { groups, unassigned } = groupByTeam(room);

  const move = (memberId: string, teamId: string) => {
    setActionError(null);
    assign.mutate({ memberId, teamId }, { onError: (e) => setActionError(e instanceof ApiError ? e.message : "Couldn't move that player.") });
  };

  const onLeave = () => leave.mutate(undefined, { onSuccess: () => router.push("/"), onError: () => setActionError("Couldn't leave the room. Try again.") });

  return (
    <div className="mx-auto w-full max-w-6xl px-5 pb-20 pt-6 sm:px-8">
      <LobbyHeader room={room} viewerIsHost={viewerIsHost} connected={connected} />

      {actionError && (
        <p role="alert" className="mt-4 rounded-lg border border-red/50 bg-red/10 px-4 py-3 text-sm">
          {actionError}
        </p>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {groups.map(({ team, members }) => (
              <TeamCard key={team.id} team={team} members={members} allTeams={room.teams} meId={room.me} viewerIsHost={viewerIsHost} onMove={move} busy={assign.isPending} />
            ))}
          </div>

          {unassigned.length > 0 && (
            <section aria-labelledby="unassigned" className="rounded-xl border border-line bg-panel px-5 pb-2 pt-4">
              <h2 id="unassigned" className="font-display text-xl font-bold">
                Waiting for a team
              </h2>
              <ul className="divide-y divide-line">
                {unassigned.map((m) => (
                  <PlayerRow key={m.id} member={m} isMe={m.id === room.me} moveTargets={viewerIsHost ? room.teams : []} onMove={(teamId) => move(m.id, teamId)} busy={assign.isPending} />
                ))}
              </ul>
            </section>
          )}
        </div>

        <div className="space-y-6">
          {me && <MyControls roomId={room.id} me={me} />}
          <StartPanel room={room} viewerIsHost={viewerIsHost} />
          <div>
            <button type="button" className={`${secondaryButton} w-full`} onClick={onLeave} disabled={leave.isPending}>
              Leave room
            </button>
            {viewerIsHost && room.member_count > 1 && <p className="mt-2 text-sm text-muted">If you leave, the longest-standing player becomes the host.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
