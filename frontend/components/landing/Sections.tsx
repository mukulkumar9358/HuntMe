"use client";

import { useMe } from "@/hooks/useAuth";

const STEPS = [
  { title: "Pick the arena", body: "The host outlines a real place on the map, somewhere everyone is allowed to be." },
  { title: "Hiders disappear", body: "Red team gets two minutes to find a spot inside the boundary." },
  { title: "Seekers hunt", body: "Blue team follows the radar and the clues. Nobody ever sees an exact location." },
  { title: "Prove the find", body: "The hider shows a one-time QR code. The seeker scans it, and both confirm." },
];

const FEATURES = [
  { title: "Hot & Cold radar", body: "One of four bands, refreshed every few seconds. No coordinates, no compass." },
  { title: "Clues from the hiders", body: "Hiders choose what to give away and when. Seekers get each clue as it lands." },
  { title: "Proof you can trust", body: "Every find is checked on the server: code, time, and how close you both are." },
  { title: "Consent-based photos", body: "A photo only happens if both players agree. Without it, the find is labelled honestly." },
  { title: "A shrinking arena", body: "Hosts can set smaller safe areas ahead of time, with a warning before each change." },
  { title: "Private team chat", body: "Hiders and seekers each get their own channel. The other side can't read it." },
];

export function HowToPlay() {
  return (
    <section id="how-to-play" className="mx-auto w-full max-w-6xl scroll-mt-8 px-5 py-16 sm:px-8">
      <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">How a round works</h2>
      <ol className="mt-10 grid gap-x-10 gap-y-8 md:grid-cols-2">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex gap-5 border-t border-line pt-5">
            <span className="font-display text-3xl font-bold text-blue" aria-hidden="true">
              {i + 1}
            </span>
            <div>
              <h3 className="text-lg font-semibold">{s.title}</h3>
              <p className="mt-1.5 max-w-md leading-relaxed text-muted">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-8 max-w-2xl text-muted">
        When the clock runs out, any hider still unfound wins for their team. Find everyone first and the seekers win.
        Then the teams swap roles.
      </p>
    </section>
  );
}

export function Features() {
  return (
    <section className="mx-auto w-full max-w-6xl px-5 py-16 sm:px-8">
      <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">Built for real streets, not screens</h2>
      <dl className="mt-10 grid gap-x-12 gap-y-9 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <div key={f.title}>
            <dt className="text-lg font-semibold">{f.title}</dt>
            <dd className="mt-1.5 leading-relaxed text-muted">{f.body}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function Safety() {
  return (
    <section className="border-y border-line bg-panel">
      <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
        <h2 className="font-display text-2xl font-bold tracking-tight">Play where you&apos;re allowed to be</h2>
        <p className="mt-3 max-w-3xl leading-relaxed text-muted">
          Stick to public spaces or places where you have permission. Stay off roads, railway tracks, rooftops and
          construction sites, and never enter private property. You can stop playing at any time.
        </p>
      </div>
    </section>
  );
}

export function RecentMatches() {
  const { data: user } = useMe();
  if (!user) return null;
  return (
    <section className="mx-auto w-full max-w-6xl px-5 py-16 sm:px-8">
      <h2 className="font-display text-3xl font-bold tracking-tight">Recent matches</h2>
      <p className="mt-4 text-muted">No matches yet. Once you&apos;ve played a round, it will show up here.</p>
    </section>
  );
}

export function SiteFooter() {
  return (
    <footer className="mx-auto w-full max-w-6xl px-5 py-10 text-sm text-muted sm:px-8">
      HuntMe. Hide. Hunt. Prove it.
    </footer>
  );
}
