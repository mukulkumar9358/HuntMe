"use client";

import { useEffect, useState } from "react";

/** The four radar bands from the game rules. Illustrative only: the real radar never shows direction. */
const BANDS = [
  { id: "cold", label: "Cold", range: "over 200 m", text: "You're far away.", r: 190, fill: "#0f1b33" },
  { id: "cool", label: "Cool", range: "100–200 m", text: "You're getting closer.", r: 140, fill: "#152a52" },
  { id: "warm", label: "Warm", range: "50–100 m", text: "Someone is nearby.", r: 90, fill: "#4a2a2e" },
  { id: "hot", label: "Hot", range: "under 50 m", text: "You're very close!", r: 45, fill: "#7a2327" },
] as const;

const GLOW: Record<string, string> = { cold: "#3b82f6", cool: "#60a5fa", warm: "#f59e0b", hot: "#ef4444" };

export function RadarDemo() {
  // Static "warm" for reduced-motion users; otherwise the bands light up in turn.
  const [active, setActive] = useState(2);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setActive((a) => (a + 1) % BANDS.length), 2400);
    return () => window.clearInterval(id);
  }, []);

  const current = BANDS[active];

  return (
    <figure className="mx-auto w-full max-w-md">
      <div className="relative aspect-square">
        <svg viewBox="-200 -200 400 400" className="h-full w-full" role="img" aria-label="Radar with four distance bands around a seeker. The hider is never shown.">
          {BANDS.map((b, i) => (
            <circle
              key={b.id}
              r={b.r}
              fill={b.fill}
              stroke={i === active ? GLOW[b.id] : "#243049"}
              strokeWidth={i === active ? 3 : 1.5}
              style={{ transition: "stroke 400ms, stroke-width 400ms", filter: i === active ? `drop-shadow(0 0 10px ${GLOW[b.id]}88)` : undefined }}
            />
          ))}
          {/* Seeker: the only dot on the map. Hiders stay hidden. */}
          <circle r="9" fill="#3b82f6" stroke="#f8fafc" strokeWidth="3" />
        </svg>
        <div
          aria-hidden="true"
          className="radar-sweep pointer-events-none absolute inset-0 rounded-full"
          style={{
            background: "conic-gradient(from 0deg, transparent 0deg, rgba(59,130,246,0.28) 50deg, transparent 52deg)",
            animation: "radar-sweep 5s linear infinite",
            clipPath: "circle(47.5%)",
          }}
        />
      </div>
      <figcaption className="mt-6">
        <p className="font-display text-4xl font-bold" style={{ color: GLOW[current.id] }}>
          {current.label}
        </p>
        <p className="mt-1 text-muted">{current.text}</p>
        <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          {BANDS.map((b) => (
            <div key={b.id} className="flex items-baseline justify-between border-b border-line pb-1.5">
              <dt className={b.id === current.id ? "font-semibold text-text" : "text-muted"}>{b.label}</dt>
              <dd className="text-muted">{b.range}</dd>
            </div>
          ))}
        </dl>
      </figcaption>
    </figure>
  );
}
