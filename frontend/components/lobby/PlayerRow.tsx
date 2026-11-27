import type { Member, Permission, Team } from "@/types/api";

const PERMISSION_TEXT: Record<Permission, string> = { GRANTED: "on", DENIED: "blocked", UNKNOWN: "not checked" };

function PermissionTag({ label, state }: { label: string; state: Permission }) {
  const color = state === "GRANTED" ? "text-green" : state === "DENIED" ? "text-red" : "text-muted";
  return (
    <span className={`text-xs ${color}`}>
      {label} {PERMISSION_TEXT[state]}
    </span>
  );
}

interface Props {
  member: Member;
  isMe: boolean;
  teamColor?: string;
  /** Set when the viewer is the host: the teams this player can be moved to. */
  moveTargets?: Team[];
  onMove?: (teamId: string) => void;
  busy?: boolean;
}

export function PlayerRow({ member, isMe, teamColor, moveTargets = [], onMove, busy }: Props) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3">
      <span
        aria-hidden="true"
        className="flex size-9 shrink-0 items-center justify-center rounded-full bg-panel-raised font-display font-bold"
        style={{ boxShadow: `0 0 0 2px ${teamColor ?? "#243049"}` }}
      >
        {member.username.slice(0, 1).toUpperCase()}
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 font-semibold">
          <span className="truncate">{member.username}</span>
          {isMe && <span className="text-xs font-normal text-muted">you</span>}
          {member.is_host && <span className="rounded bg-blue/20 px-1.5 py-0.5 text-xs font-semibold text-blue-soft">Host</span>}
        </p>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <span aria-hidden="true" className={`size-2 rounded-full ${member.online ? "bg-green" : "bg-line"}`} />
            {member.online ? "Online" : "Offline"}
          </span>
          <PermissionTag label="Location" state={member.location_permission} />
          <PermissionTag label="Camera" state={member.camera_permission} />
        </p>
      </div>
      <span className={`text-sm font-semibold ${member.is_ready ? "text-green" : "text-muted"}`}>{member.is_ready ? "Ready" : "Not ready"}</span>
      {moveTargets.length > 0 && onMove && (
        <div className="flex w-full gap-2 sm:w-auto">
          {moveTargets.map((t) => (
            <button
              key={t.id}
              type="button"
              disabled={busy}
              onClick={() => onMove(t.id)}
              aria-label={`Move ${member.username} to ${t.name}`}
              className="rounded-md border border-line px-3 py-1.5 text-sm hover:bg-panel-raised disabled:opacity-60"
            >
              Move to {t.name}
            </button>
          ))}
        </div>
      )}
    </li>
  );
}
