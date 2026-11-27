"use client";

import Link from "next/link";

import { Logo } from "@/components/common/Logo";
import { primaryButton, secondaryButton } from "@/components/common/buttons";
import { useLogout, useMe } from "@/hooks/useAuth";

export function SiteHeader() {
  const { data: user, isPending } = useMe();
  const logout = useLogout();

  return (
    <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
      <Logo />
      <nav aria-label="Account" className="flex min-h-11 items-center gap-3">
        {isPending ? null : user ? (
          <>
            <span className="hidden text-sm text-muted sm:inline">
              Signed in as <span className="font-semibold text-text">{user.username}</span>
            </span>
            <button type="button" className={`${secondaryButton} !py-2 !text-sm`} disabled={logout.isPending} onClick={() => logout.mutate()}>
              Log out
            </button>
          </>
        ) : (
          <>
            <Link href="/login" className="px-3 py-2 text-sm font-semibold text-muted hover:text-text">
              Log in
            </Link>
            <Link href="/register" className={`${primaryButton} !py-2 !text-sm`}>
              Sign up
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
