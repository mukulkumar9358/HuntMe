"use client";

import { LobbyView } from "@/components/lobby/LobbyView";

// Thin client boundary so the server page can pass the route param straight through.
export function LobbyViewLoader({ roomId }: { roomId: string }) {
  return <LobbyView roomId={roomId} />;
}
