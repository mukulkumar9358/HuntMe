"use client";

import Link from "next/link";

import { primaryButton } from "@/components/common/buttons";
import { JoinForm } from "@/components/landing/JoinForm";
import { RadarDemo } from "@/components/radar/RadarDemo";
import { useMe } from "@/hooks/useAuth";

export function Hero() {
  const { data: user } = useMe();

  return (
    <section className="mx-auto grid w-full max-w-6xl items-center gap-14 px-5 pb-20 pt-8 sm:px-8 lg:grid-cols-[1.05fr_0.95fr] lg:pt-14">
      <div>
        <h1 className="font-display text-5xl font-extrabold leading-[1.02] tracking-tight sm:text-7xl">
          Hide.
          <br />
          Hunt.
          <br />
          Prove it.
        </h1>
        <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted">
          Real-world hide-and-seek for two teams. Pick a real place, split into hiders and seekers, and track each other
          down with nothing but a Hot &amp; Cold radar and a few clues.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link href={user ? "/create-room" : "/register?next=/create-room"} className={primaryButton}>
            Create game
          </Link>
          <JoinForm />
        </div>
        {!user && (
          <p className="mt-4 text-sm text-muted">
            You need a free account to play.{" "}
            <Link href="/login" className="font-semibold text-blue-soft underline underline-offset-4">
              Log in
            </Link>
          </p>
        )}
      </div>
      <RadarDemo />
    </section>
  );
}
