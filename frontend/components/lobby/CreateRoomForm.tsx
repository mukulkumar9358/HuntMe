"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { TextField } from "@/components/auth/TextField";
import { primaryButton } from "@/components/common/buttons";
import { useCreateRoom, useGameConfig } from "@/hooks/useRooms";
import { inviteStore } from "@/lib/lobby";
import { ApiError } from "@/services/api";
import type { GameConfig, Range } from "@/types/api";

function buildSchema(c: GameConfig) {
  const num = (label: string, r: Range) =>
    z.number({ error: "Enter a number." }).int("Use a whole number.").min(r.min, `${label}: at least ${r.min}.`).max(r.max, `${label}: at most ${r.max}.`);
  return z.object({
    room_name: z.string().trim().min(c.room_name_length.min, `Use at least ${c.room_name_length.min} characters.`).max(c.room_name_length.max, `Use ${c.room_name_length.max} characters or fewer.`),
    max_players: num("Players", c.max_players),
    hide_duration_seconds: num("Hiding time", c.hide_duration_seconds),
    hunt_duration_seconds: num("Hunting time", c.hunt_duration_seconds),
    clue_interval_seconds: num("Clue interval", c.clue_interval_seconds),
    shrinking_zone_enabled: z.boolean(),
    join_policy: z.enum(["CODE", "INVITE_ONLY"]),
    team_mode: z.enum(["auto", "manual"]),
  });
}
type Values = z.infer<ReturnType<typeof buildSchema>>;

const range = (r: Range, unit: string) => `${r.min}–${r.max} ${unit}`;

export function CreateRoomForm() {
  const { data: config, isError, refetch } = useGameConfig();
  if (isError) {
    return (
      <p role="alert" className="text-muted">
        Couldn&apos;t load the game settings.{" "}
        <button className="font-semibold text-blue-soft underline underline-offset-4" onClick={() => void refetch()}>
          Try again
        </button>
      </p>
    );
  }
  return config ? <Form config={config} /> : <p className="text-muted">Loading settings…</p>;
}

function Form({ config }: { config: GameConfig }) {
  const router = useRouter();
  const create = useCreateRoom();
  const [formError, setFormError] = useState<string | null>(null);
  const schema = useMemo(() => buildSchema(config), [config]);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      room_name: "",
      max_players: config.max_players.default,
      hide_duration_seconds: config.hide_duration_seconds.default,
      hunt_duration_seconds: config.hunt_duration_seconds.default,
      clue_interval_seconds: config.clue_interval_seconds.default,
      shrinking_zone_enabled: false,
      join_policy: "CODE",
      team_mode: "auto",
    },
  });

  const onSubmit = handleSubmit(async ({ team_mode, ...v }) => {
    setFormError(null);
    try {
      const created = await create.mutateAsync({ ...v, auto_balance_teams: team_mode === "auto" });
      inviteStore.set(created.room.id, created.invite_token);
      router.push(`/lobby/${created.room.id}`);
    } catch (e) {
      if (!(e instanceof ApiError)) return setFormError("Something went wrong. Try again.");
      const first = e.code === "validation_error" ? e.details?.[0] : undefined;
      if (first && first.field in v) return setError(first.field as keyof Values, { message: first.message });
      setFormError(e.code === "rate_limited" ? "You're creating rooms too quickly. Wait a minute and try again." : e.message);
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-7">
      {formError && (
        <p role="alert" className="rounded-lg border border-red/50 bg-red/10 px-4 py-3 text-sm">
          {formError}
        </p>
      )}
      <TextField label="Room name" placeholder="Saturday hunt" error={errors.room_name?.message} {...register("room_name")} />
      <TextField
        label="Players"
        type="number"
        inputMode="numeric"
        hint={`${range(config.max_players, "players")}. Two teams, red and blue.`}
        error={errors.max_players?.message}
        {...register("max_players", { valueAsNumber: true })}
      />
      <div className="grid gap-5 sm:grid-cols-3">
        <TextField label="Hiding time (seconds)" type="number" inputMode="numeric" hint={range(config.hide_duration_seconds, "s")} error={errors.hide_duration_seconds?.message} {...register("hide_duration_seconds", { valueAsNumber: true })} />
        <TextField label="Hunting time (seconds)" type="number" inputMode="numeric" hint={range(config.hunt_duration_seconds, "s")} error={errors.hunt_duration_seconds?.message} {...register("hunt_duration_seconds", { valueAsNumber: true })} />
        <TextField label="Clue every (seconds)" type="number" inputMode="numeric" hint={range(config.clue_interval_seconds, "s")} error={errors.clue_interval_seconds?.message} {...register("clue_interval_seconds", { valueAsNumber: true })} />
      </div>

      <fieldset>
        <legend className="mb-2 text-sm font-semibold">Who can join</legend>
        <div className="space-y-2">
          <label className="flex items-start gap-3">
            <input type="radio" value="CODE" className="mt-1" {...register("join_policy")} />
            <span>Anyone with the room code</span>
          </label>
          <label className="flex items-start gap-3">
            <input type="radio" value="INVITE_ONLY" className="mt-1" {...register("join_policy")} />
            <span>Invite link only</span>
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-sm font-semibold">Teams</legend>
        <div className="space-y-2">
          <label className="flex items-start gap-3">
            <input type="radio" value="auto" className="mt-1" {...register("team_mode")} />
            <span>Balance teams automatically as people join</span>
          </label>
          <label className="flex items-start gap-3">
            <input type="radio" value="manual" className="mt-1" {...register("team_mode")} />
            <span>I&apos;ll put players on teams myself</span>
          </label>
        </div>
        <p className="mt-2 text-sm text-muted">You can move anyone between teams in the lobby either way.</p>
      </fieldset>

      <label className="flex items-start gap-3">
        <input type="checkbox" className="mt-1" {...register("shrinking_zone_enabled")} />
        <span>
          Shrinking safe zone
          <span className="block text-sm text-muted">You&apos;ll choose the smaller safe areas when you set up the arena.</span>
        </span>
      </label>

      <button type="submit" className={`${primaryButton} w-full sm:w-auto`} disabled={create.isPending}>
        {create.isPending ? "Creating…" : "Create room"}
      </button>
    </form>
  );
}
