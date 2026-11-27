import Link from "next/link";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 font-display text-xl font-bold tracking-tight" aria-label="HuntMe home">
      <svg width="28" height="28" viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r="26" fill="none" stroke="#243049" strokeWidth="5" />
        <circle cx="32" cy="32" r="15" fill="none" stroke="#3b82f6" strokeWidth="5" />
        <circle cx="32" cy="32" r="5" fill="#ef4444" />
      </svg>
      HuntMe
    </Link>
  );
}
