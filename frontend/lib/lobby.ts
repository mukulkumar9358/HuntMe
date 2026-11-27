import type { Blocker, Member, RoomDetail, Team } from "@/types/api";

export const SAFETY_RULES = [
  "Only play in public spaces or places where you have permission to be.",
  "Stay off roads, railway tracks, rooftops and construction sites, and never enter private property.",
  "Don't block or bother other people, and don't photograph anyone who isn't playing.",
  "You can stop playing and leave the game at any time.",
];

/** Friendly text for each reason the host can't start yet. Codes come from the backend. */
export function blockerMessage(b: Blocker): string {
  const n = b.detail ? Number(b.detail) : 0;
  switch (b.code) {
    case "need_two_players":
      return "At least two players need to be on teams.";
    case "team_empty":
      return `Team ${b.detail ?? ""} needs at least one player.`.replace("  ", " ");
    case "unassigned_members":
      return n === 1 ? "1 player still needs a team." : `${n} players still need a team.`;
    case "host_not_ready":
      return "You need to mark yourself ready.";
    case "safety_unacknowledged":
      return n === 1 ? "1 player hasn't accepted the safety rules." : `${n} players haven't accepted the safety rules.`;
    case "arena_missing":
      return "No playing area has been set yet.";
    default:
      return "Something isn't ready yet.";
  }
}

export interface TeamGroup {
  team: Team;
  members: Member[];
}

export function groupByTeam(room: Pick<RoomDetail, "teams" | "members">): { groups: TeamGroup[]; unassigned: Member[] } {
  const teams = [...room.teams].sort((a, b) => a.position - b.position);
  return {
    groups: teams.map((team) => ({ team, members: room.members.filter((m) => m.team_id === team.id) })),
    unassigned: room.members.filter((m) => m.team_id === null),
  };
}

export function formatDuration(seconds: number): string {
  if (seconds < 90) return `${seconds} sec`;
  const minutes = seconds / 60;
  return Number.isInteger(minutes) ? `${minutes} min` : `${minutes.toFixed(1)} min`;
}

export function inviteUrl(origin: string, token: string): string {
  return `${origin}/join-room?invite=${encodeURIComponent(token)}`;
}

/** Why the Ready button is unavailable, or null when it can be used. Mirrors the server rules. */
export function readyBlockReason(me: Member | undefined): string | null {
  if (!me) return null;
  if (me.team_id === null) return "Wait for the host to put you on a team.";
  if (!me.safety_acknowledged) return "Accept the safety rules first.";
  return null;
}

const INVITE_KEY = (roomId: string) => `huntme:invite:${roomId}`;

/** Invite tokens are only returned once; keep the host's in this tab so the link can be re-copied. */
export const inviteStore = {
  get: (roomId: string): string | null => {
    try {
      return sessionStorage.getItem(INVITE_KEY(roomId));
    } catch {
      return null;
    }
  },
  set: (roomId: string, token: string): void => {
    try {
      sessionStorage.setItem(INVITE_KEY(roomId), token);
    } catch {
      /* storage unavailable: the host can generate a new link instead */
    }
  },
};
