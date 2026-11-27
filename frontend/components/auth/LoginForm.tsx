"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { AuthShell } from "@/components/auth/AuthShell";
import { TextField } from "@/components/auth/TextField";
import { primaryButton } from "@/components/common/buttons";
import { useLogin } from "@/hooks/useAuth";
import { type LoginValues, loginSchema, safeNext } from "@/lib/validation";
import { ApiError } from "@/services/api";

export function LoginForm() {
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const login = useLogin();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await login.mutateAsync(values);
      router.push(next);
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    }
  });

  return (
    <AuthShell
      title="Log in"
      subtitle="Welcome back. Your teams are waiting."
      footer={
        <>
          New to HuntMe?{" "}
          <Link href={next === "/" ? "/register" : `/register?next=${encodeURIComponent(next)}`} className="font-semibold text-blue-soft underline underline-offset-4">
            Create an account
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
        <TextField label="Email or username" autoComplete="username" error={errors.identifier?.message} {...register("identifier")} />
        <TextField label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...register("password")} />
        <button type="submit" className={`${primaryButton} w-full`} disabled={login.isPending}>
          {login.isPending ? "Logging in…" : "Log in"}
        </button>
      </form>
    </AuthShell>
  );
}
