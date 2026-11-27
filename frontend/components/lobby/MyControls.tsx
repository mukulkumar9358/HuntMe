"use client";

import { useEffect, useRef, useState } from "react";

import { primaryButton, secondaryButton } from "@/components/common/buttons";
import { useUpdateMyState } from "@/hooks/useRooms";
import { SAFETY_RULES, readyBlockReason } from "@/lib/lobby";
import { queryPermission, requestCamera, requestLocation } from "@/lib/permissions";
import { ApiError } from "@/services/api";
import type { Member, Permission } from "@/types/api";

function PermissionRow({ label, state, onRequest, pending }: { label: string; state: Permission; onRequest: () => void; pending: boolean }) {
  const text = state === "GRANTED" ? "Allowed" : state === "DENIED" ? "Blocked in your browser settings" : "Not allowed yet";
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div>
        <p className="font-semibold">{label}</p>
        <p className={`text-sm ${state === "GRANTED" ? "text-green" : state === "DENIED" ? "text-red" : "text-muted"}`}>{text}</p>
      </div>
      {state !== "GRANTED" && (
        <button type="button" className={`${secondaryButton} !px-4 !py-2 !text-sm`} onClick={onRequest} disabled={pending}>
          Allow {label.toLowerCase()}
        </button>
      )}
    </div>
  );
}

export function MyControls({ roomId, me }: { roomId: string; me: Member }) {
  const update = useUpdateMyState(roomId);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState<"location" | "camera" | null>(null);
  const synced = useRef(false);

  // Once on mount, reflect what the browser already knows (e.g. permission granted on a previous visit).
  useEffect(() => {
    if (synced.current) return;
    synced.current = true;
    void (async () => {
      const [loc, cam] = await Promise.all([queryPermission("geolocation"), queryPermission("camera")]);
      const patch: { location_permission?: Permission; camera_permission?: Permission } = {};
      if (loc && loc !== "UNKNOWN" && loc !== me.location_permission) patch.location_permission = loc;
      if (cam && cam !== "UNKNOWN" && cam !== me.camera_permission) patch.camera_permission = cam;
      if (Object.keys(patch).length) update.mutate(patch);
    })();
  }, [me.location_permission, me.camera_permission, update]);

  const run = (fn: () => Promise<unknown>) => {
    setError(null);
    fn().catch((e) => setError(e instanceof ApiError ? e.message : "Something went wrong. Try again."));
  };
  const send = (patch: Parameters<typeof update.mutateAsync>[0]) => run(() => update.mutateAsync(patch));

  const ask = (kind: "location" | "camera") =>
    run(async () => {
      setAsking(kind);
      try {
        const state = await (kind === "location" ? requestLocation() : requestCamera());
        await update.mutateAsync(kind === "location" ? { location_permission: state } : { camera_permission: state });
      } finally {
        setAsking(null);
      }
    });

  const blockReason = readyBlockReason(me);

  return (
    <section aria-labelledby="my-controls" className="rounded-xl border border-line bg-panel p-5">
      <h2 id="my-controls" className="font-display text-xl font-bold">
        Your setup
      </h2>
      {error && (
        <p role="alert" className="mt-3 rounded-lg border border-red/50 bg-red/10 px-4 py-2 text-sm">
          {error}
        </p>
      )}

      <div className="mt-4">
        <p className="font-semibold">Safety rules</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
          {SAFETY_RULES.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <label className="mt-3 flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1"
            checked={me.safety_acknowledged}
            disabled={update.isPending}
            onChange={(e) => send({ safety_acknowledged: e.target.checked })}
          />
          <span>I&apos;ve read the safety rules and will follow them.</span>
        </label>
      </div>

      <div className="mt-5 divide-y divide-line border-t border-line">
        <PermissionRow label="Location" state={me.location_permission} pending={asking !== null} onRequest={() => ask("location")} />
        <PermissionRow label="Camera" state={me.camera_permission} pending={asking !== null} onRequest={() => ask("camera")} />
      </div>
      <p className="mt-2 text-sm text-muted">Your browser only shares your location and camera while the game is open and running.</p>

      <div className="mt-5">
        <button
          type="button"
          className={me.is_ready ? `${secondaryButton} w-full` : `${primaryButton} w-full`}
          disabled={update.isPending || (!me.is_ready && blockReason !== null)}
          aria-describedby={blockReason ? "ready-reason" : undefined}
          onClick={() => send({ is_ready: !me.is_ready })}
        >
          {me.is_ready ? "I'm not ready" : "I'm ready"}
        </button>
        {blockReason && !me.is_ready && (
          <p id="ready-reason" className="mt-2 text-sm text-muted">
            {blockReason}
          </p>
        )}
      </div>
    </section>
  );
}
