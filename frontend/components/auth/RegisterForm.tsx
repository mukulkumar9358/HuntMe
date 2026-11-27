"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { AuthShell } from "@/components/auth/AuthShell";
import { TextField } from "@/components/auth/TextField";
import { primaryButton } from "@/components/common/buttons";
import { useRegister } from "@/hooks/useAuth";
import { type RegisterValues, registerSchema, safeNext } from "@/lib/validation";
import { ApiError } from "@/services/api";

type Field = keyof RegisterValues;
const SERVER_FIELD: Record<string, Field> = { username_taken: "username", email_taken: "email" };

export function RegisterForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const signUp = useRegister();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) });

  const onSubmit = handleSubmit(async ({ username, email, password }) => {
    setFormError(null);
    try {
      await signUp.mutateAsync({ username, email, password });
      router.push(next);
    } catch (e) {
      if (!(e instanceof ApiError)) return setFormError("Something went wrong. Try again.");
      const field = SERVER_FIELD[e.code];
      if (field) return setError(field, { message: e.message });
      if (e.code === "validation_error" && e.details?.length) {
        let placed = false;
        for (const d of e.details) {
          if (["username", "email", "password"].includes(d.field)) {
            setError(d.field as Field, { message: d.message });
            placed = true;
          }
        }
        if (placed) return;
      }
      setFormError(e.message);
    }
  });

  return (
    <AuthShell
      title="Create your account"
      subtitle="Pick a username your friends will recognise."
      footer={
        <>
          Already have an account?{" "}
          <Link href={next === "/" ? "/login" : `/login?next=${encodeURIComponent(next)}`} className="font-semibold text-blue-soft underline underline-offset-4">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        {formError && (
          <p role="alert" className="rounded-lg border border-red/50 bg-red/10 px-4 py-3 text-sm">
            {formError}
          </p>
        )}
        <TextField label="Username" autoComplete="username" hint="3–24 letters, numbers or underscores." error={errors.username?.message} {...register("username")} />
        <TextField label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register("email")} />
        <TextField label="Password" type="password" autoComplete="new-password" hint="At least 10 characters." error={errors.password?.message} {...register("password")} />
        <TextField label="Confirm password" type="password" autoComplete="new-password" error={errors.confirmPassword?.message} {...register("confirmPassword")} />
        <button type="submit" className={`${primaryButton} w-full`} disabled={signUp.isPending}>
          {signUp.isPending ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthShell>
  );
}
