import { PlayerRow } from "@/components/lobby/PlayerRow";
import type { Member, Team } from "@/types/api";

interface Props {
  team: Team;
  members: Member[];
  allTeams: Team[];
  meId: string;
  viewerIsHost: boolean;
  onMove: (memberId: string, teamId: string) => void;
  busy: boolean;
}

export function TeamCard({ team, members, allTeams, meId, viewerIsHost, onMove, busy }: Props) {
  return (
    <section aria-labelledby={`team-${team.id}`} className="rounded-xl border border-line bg-panel" style={{ borderTop: `4px solid ${team.color}` }}>
      <div className="flex items-baseline justify-between px-5 pt-4">
        <h2 id={`team-${team.id}`} className="font-display text-2xl font-bold" style={{ color: team.color }}>
          Team {team.name}
        </h2>
        <span className="text-sm text-muted">{members.length === 1 ? "1 player" : `${members.length} players`}</span>
      </div>
      {members.length === 0 ? (
        <p className="px-5 pb-5 pt-3 text-muted">No players yet.</p>
      ) : (
        <ul className="divide-y divide-line px-5 pb-2">
          {members.map((m) => (
            <PlayerRow
              key={m.id}
              member={m}
              isMe={m.id === meId}
              teamColor={team.color}
              moveTargets={viewerIsHost ? allTeams.filter((t) => t.id !== team.id) : []}
              onMove={(teamId) => onMove(m.id, teamId)}
              busy={busy}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
