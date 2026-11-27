import type { Metadata } from "next";

import { RequireAuth } from "@/components/common/RequireAuth";
import { LobbyViewLoader } from "@/components/lobby/LobbyViewLoader";

export const metadata: Metadata = { title: "Lobby" };

export default async function LobbyPage({ params }: { params: Promise<{ roomId: string }> }) {
  const { roomId } = await params;
  return (
    <RequireAuth>
      <LobbyViewLoader roomId={roomId} />
    </RequireAuth>
  );
}
