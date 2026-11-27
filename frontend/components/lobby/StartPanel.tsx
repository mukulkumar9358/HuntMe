import { blockerMessage } from "@/lib/lobby";
import type { RoomDetail } from "@/types/api";

/**
 * Starting a match arrives with the game engine. Until then this shows the host exactly what is still
 * missing, using the server's own list, and the button stays disabled.
 */
export function StartPanel({ room, viewerIsHost }: { room: RoomDetail; viewerIsHost: boolean }) {
  const host = room.members.find((m) => m.is_host);
  if (!viewerIsHost) {
    return (
      <section className="rounded-xl border border-line bg-panel p-5">
        <p className="text-muted">Waiting for {host?.username ?? "the host"} to start the game.</p>
      </section>
    );
  }
  return (
    <section aria-labelledby="start-heading" className="rounded-xl border border-line bg-panel p-5">
      <h2 id="start-heading" className="font-display text-xl font-bold">
        Start the game
      </h2>
      {room.start_blockers.length > 0 ? (
        <>
          <p className="mt-2 text-sm text-muted">Still to do before you can start:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {room.start_blockers.map((b) => (
              <li key={`${b.code}-${b.detail ?? ""}`}>{blockerMessage(b)}</li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-2 text-sm text-green">Everything is ready.</p>
      )}
      {room.teams_unbalanced && <p className="mt-3 text-sm text-amber">The teams are uneven. That&apos;s allowed, but you may want to balance them.</p>}
      <button type="button" disabled className="mt-4 w-full cursor-not-allowed rounded-lg bg-blue px-5 py-3 font-semibold text-white opacity-50">
        Start game
      </button>
    </section>
  );
}
