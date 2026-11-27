import type { FieldError } from "@/types/api";

const BASE = "/api/v1";
const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
// Requests that must never trigger a silent refresh-and-retry.
const NO_REFRESH = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"];

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: FieldError[],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : "";
}

let refreshInFlight: Promise<boolean> | null = null;

/** One refresh at a time; concurrent 401s share the same attempt. */
function refreshSession(): Promise<boolean> {
  refreshInFlight ??= fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-Token": readCookie("csrf_token") },
  })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const e = body?.error;
    return new ApiError(res.status, e?.code ?? `http_${res.status}`, e?.message ?? "Something went wrong.", Array.isArray(e?.details) ? e.details : undefined);
  } catch {
    return new ApiError(res.status, `http_${res.status}`, "Something went wrong.");
  }
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = init.method ?? "GET";
  const send = () =>
    fetch(`${BASE}${path}`, {
      method,
      credentials: "include",
      headers: {
        ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(UNSAFE.has(method) ? { "X-CSRF-Token": readCookie("csrf_token") } : {}),
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });

  let res: Response;
  try {
    res = await send();
  } catch {
    throw new ApiError(0, "network_error", "Can't reach HuntMe. Check your connection and try again.");
  }

  if (res.status === 401 && !NO_REFRESH.includes(path) && (await refreshSession())) {
    res = await send();
  }
  if (!res.ok) throw await parseError(res);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
