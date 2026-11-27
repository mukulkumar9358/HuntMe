import type { Metadata } from "next";

import { RequireAuth } from "@/components/common/RequireAuth";
import { CreateRoomForm } from "@/components/lobby/CreateRoomForm";

export const metadata: Metadata = { title: "Create game" };

export default function CreateRoomPage() {
  return (
    <RequireAuth>
      <div className="mx-auto w-full max-w-xl px-5 pb-20 pt-10 sm:pt-14">
        <h1 className="font-display text-4xl font-bold tracking-tight">Create a game</h1>
        <p className="mb-8 mt-2 text-muted">Set the rules, then invite your friends. You&apos;ll choose the playing area next.</p>
        <CreateRoomForm />
      </div>
    </RequireAuth>
  );
}
