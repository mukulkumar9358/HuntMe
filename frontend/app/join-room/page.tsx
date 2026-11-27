import type { Metadata } from "next";
import { createElement, Suspense } from "react";

import { RequireAuth } from "@/components/common/RequireAuth";
import { JoinRoomForm } from "@/components/lobby/JoinRoomForm";

export const metadata: Metadata = { title: "Join game" };

export default function JoinRoomPage() {
  return createElement(
    RequireAuth,
    null,
    createElement(
      "div",
      { className: "mx-auto w-full max-w-md px-5 pb-20 pt-10 sm:pt-14" },
      createElement(
        "h1",
        { className: "font-display text-4xl font-bold tracking-tight" },
        "Join a game",
      ),
      createElement(
        "p",
        { className: "mb-8 mt-2 text-muted" },
        "Enter the code your host shared with you.",
      ),
      createElement(Suspense, null, createElement(JoinRoomForm)),
    ),
  );
}
