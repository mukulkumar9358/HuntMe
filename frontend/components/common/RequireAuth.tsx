"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useMe } from "@/hooks/useAuth";

/** Client-side gate for signed-in pages. The API enforces auth independently. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data: user, isPending } = useMe();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Keep the query string so invite links (/join-room?invite=...) survive the trip through login.
    if (!isPending && !user) router.replace(`/login?next=${encodeURIComponent(pathname + window.location.search)}`);
  }, [isPending, user, router, pathname]);

  if (isPending || !user) return <p className="mx-auto max-w-6xl px-5 py-16 text-muted sm:px-8">Loading…</p>;
  return <>{children}</>;
}
