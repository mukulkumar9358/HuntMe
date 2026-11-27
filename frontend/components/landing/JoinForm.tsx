"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { secondaryButton } from "@/components/common/buttons";

export function JoinForm() {
  const router = useRouter();
  const [code, setCode] = useState("");

  return (
    <form
      className="flex w-full max-w-sm gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const trimmed = code.trim().toUpperCase();
        if (trimmed) router.push(`/join-room?code=${encodeURIComponent(trimmed)}`);
      }}
    >
      <label htmlFor="room-code" className="sr-only">
        Room code
      </label>
      <input
        id="room-code"
        value={code}
        onChange={(e) => setCode(e.target.value)}
        placeholder="Room code"
        autoCapitalize="characters"
        autoComplete="off"
        maxLength={12}
        className="min-w-0 flex-1 rounded-lg border border-line bg-panel px-4 py-3 font-semibold uppercase tracking-widest text-text placeholder:font-normal placeholder:normal-case placeholder:tracking-normal placeholder:text-muted"
      />
      <button type="submit" className={secondaryButton} disabled={!code.trim()}>
        Join game
      </button>
    </form>
  );
}
