# Deploying HuntMe to Render + Neon (₹0)

Architecture: **Render** frontend (Next.js) + backend (FastAPI) + Key Value (Redis-compatible), **Neon** PostgreSQL + PostGIS. Everything on free plans. Local Docker Compose is untouched and keeps working.

```
Browser ──https──▶ Render frontend (Next.js) ──https /api/v1 rewrite──▶ Render backend (FastAPI) ──▶ Neon (PostGIS)
   │                                                                          │
   └────────────── wss (direct, single-use ticket) ──────────────────────────┘ ──private──▶ Render Key Value
```

## What changed in the code

| File | Change |
|---|---|
| `backend/app/infrastructure/ws_ticket.py` (new) | Single-use WebSocket tickets in Key Value (hashed, room-bound, atomic `GETDEL`, 30 s TTL) |
| `backend/app/api/routes/rooms.py` | `POST /api/v1/rooms/{id}/ws-ticket` (CSRF + session + room membership + rate limit) |
| `backend/app/websocket/lobby.py` | Accepts a ticket via `Sec-WebSocket-Protocol` (never in the URL/logs). Cookie auth still works locally. Origin + membership checks unchanged |
| `backend/app/core/config.py` | Accepts Neon's URL as-is (`postgresql://…?sslmode=require&channel_binding=require` → asyncpg form); pool settings |
| `backend/app/infrastructure/database.py` | Configurable small pool, `pool_recycle` (Neon suspends idle computes) |
| `frontend/hooks/useLobbySocket.ts` | Fetches a fresh ticket per (re)connect when the API host ≠ page host; same-host (local) unchanged |
| `frontend/next.config.ts` | HSTS header |
| `backend/tests/test_ws_ticket.py`, `frontend/tests/useLobbySocket.test.tsx` | New tests |
| `render.yaml`, `.github/workflows/ci.yml`, `.github/workflows/verify-deploy.yml`, `.env.production.example`, `docs/DEPLOY.md` (new) | Deployment + CI |

Not touched: `docker-compose.yml`, your `.env`, volumes, migrations, Dockerfiles.

> **I could not run the test suites or a real deployment in my environment** (no Python/Node packages installable, no Postgres/Redis). The code is syntax-checked only. **Step 1 below runs everything locally first**; don't skip it.

---

## Step 1 — Test before deploying

**Backend tests:** the simplest route is to let GitHub Actions run them (Step 3 opens a pull request; CI spins up its own throwaway PostGIS + Redis). Don't merge until they're green. To run them locally instead (PowerShell, from the repo root; replace `YOURPASS` with your local `POSTGRES_PASSWORD`):

```powershell
docker compose up -d huntme-db huntme-redis
docker compose exec huntme-db psql -U huntme -c "CREATE DATABASE huntme_test;"   # "already exists" is fine
docker run --rm --network huntme_default -v "${PWD}/backend:/app" -w /app `
  -e TEST_DATABASE_URL=postgresql+asyncpg://huntme:YOURPASS@huntme-db:5432/huntme_test `
  -e TEST_REDIS_URL=redis://huntme-redis:6379/1 `
  python:3.12-slim sh -c "pip install -q -r requirements-dev.txt && pytest -q"
```
`huntme_test` is a separate database that the tests wipe; never point `TEST_DATABASE_URL` at your real `huntme` database. (`huntme_default` is the compose network name; check with `docker network ls` if yours differs.)

**Frontend:**

```bash
cd frontend && npm ci && npm run lint && npm run typecheck && npm test && npm run build
```

Then `docker compose up --build` and confirm the app still works at your usual local URL (create a room, join from a second browser, presence updates live). Fix anything red before continuing.

## Step 2 — Neon (database)

1. Sign up at neon.com (free, no card). Create a project: **Postgres 16**, region **AWS Singapore (ap-southeast-1)**.
2. SQL Editor → run `CREATE EXTENSION IF NOT EXISTS postgis;` then `SELECT PostGIS_Version();`. (Migration 0001 also does this; running it here first proves PostGIS works on your project.)
3. **Connect** dialog → turn **Connection pooling OFF** → copy the connection string (host without `-pooler`). Keep it secret. Use the direct endpoint because Alembic runs on it and asyncpg + the pooler need extra statement-cache settings.
4. You do **not** need to edit the string; the app converts it.

## Step 3 — Push to GitHub

```bash
git checkout -b deploy-setup
git add . && git commit -m "Add Render deployment, WebSocket tickets, CI"
git push -u origin deploy-setup
```
Open a pull request into `main`; wait for **CI** to go green (Actions tab); merge. (Fix `ci.yml` failures first; Render won't deploy `main` until checks pass.)

Make sure the repo has `.env` ignored (it is, via `.gitignore`) and **no secrets** are committed.

## Step 4 — Render

1. Sign up at render.com with GitHub. Free plan, no card needed for free instances.
2. **Check names are available**: New → Web Service and try the names `huntme-frontend` / `huntme-backend`. If taken, pick unique ones (e.g. `huntme-mukul-api`) and edit **both** `render.yaml` service names and the four URL variables in it (`FRONTEND_URL`, `BACKEND_URL`, `BACKEND_INTERNAL_URL`, `NEXT_PUBLIC_WS_URL`). Frontend URL = `https://<frontend-name>.onrender.com`; WebSocket URL = `wss://<backend-name>.onrender.com`.
3. **New → Blueprint** → pick the `HuntMe` repo, branch `main`. Render reads `render.yaml` and shows 3 resources, all **Free**. It asks for `DATABASE_URL` → paste the Neon string. Apply.
4. First builds take several minutes. Watch the backend log: you should see Alembic run `0001` and `0002` then Uvicorn start.
5. In the **frontend build log**, confirm the build happened with your backend URL. Render passes service env vars to Docker as build args (the Dockerfile declares `ARG BACKEND_INTERNAL_URL` / `ARG NEXT_PUBLIC_WS_URL`). If the app later proxies to the wrong place, change the ARG defaults in `frontend/Dockerfile` to your real URLs and redeploy.

Region: keep Render services in **Singapore** to match Neon; if Render's Singapore option isn't offered for free Key Value in your account, pick the same region for all three Render resources and note the extra latency.

## Step 5 — Verify

From your repo's Actions tab → **Verify production** → Run workflow (first set repository **variables** `FRONTEND_URL`, `BACKEND_URL`). It checks `/health`, `/health/ready` (DB + PostGIS + Key Value), the frontend page, and that the frontend proxy reaches the API.

Then manually, with **two different browsers** (or phone on mobile data):
- Register, log out, log in, reload (refresh token path).
- Create a room; join from the second browser with the code; and via an invite link.
- Change teams, ready status; host controls; see presence flip online/offline live.
- Turn Wi-Fi off/on on one device: the lobby should reconnect.
- Leave the room: the other browser should update.
- Browser dev tools → Network → WS: the request URL has **no** token in it; the Cookie header is absent; the `huntme.ticket` subprotocol is negotiated.

### Client IP / proxy hops (`TRUSTED_PROXY_HOPS`)
Rate limits are keyed by client IP, read from the `X-Forwarded-For` chain counted **from the right**. I set `2` as a starting value but **could not measure Render's real chain**. If it is too low, every user shares one rate-limit bucket (the proxy's), so after ~10 login attempts across *all* users everyone gets 429. Test: from network A, fail logging in 10 times; then from network B (phone data), try logging in. If B is also rate-limited → raise `TRUSTED_PROXY_HOPS` to `3` (Render dashboard → backend → Environment) and retest. If A is not limited at all after 11 tries, it's too high (spoofable); lower it.

## Step 6 — Everyday workflow (automatic deploys)

```
edit in VS Code → test with local Docker → git push (branch) → PR → CI green → merge to main
   → Render sees checks pass → rebuilds & deploys → (optional) run "Verify production"
```
`autoDeployTrigger: checksPass` makes Render wait for the GitHub checks. Migrations run automatically at backend start (`alembic upgrade head`). Rules for safe schema changes: add columns/tables in new migration files, never edit applied migrations, and avoid destructive changes in one step (add → backfill → switch → remove later). Neon free has no point-in-time restore beyond a short window, so before risky migrations create a Neon **branch** (free) as a backup.

Optional but recommended: GitHub → Settings → Branches → protect `main`, require the `Backend` and `Frontend` checks. Without this, a direct push to `main` can still go live if its checks pass later than Render's check wait.

## Free-tier limits (be honest with yourself)

- **Render free web services sleep after 15 min idle**; first request wakes them (~1 minute). The frontend and backend sleep independently, so a cold visit can show errors/timeouts for the first minute. Refresh after waiting. There is no free fix; keep-alive pingers would only drain the shared **750 instance-hours/month** (two always-on services need ~1,488), and running out suspends all free services until next month.
- Backend start runs `alembic upgrade head` on every wake-up (a no-op when current, but adds seconds and wakes Neon).
- **Free Key Value is memory-only** and can be wiped on restart: in-flight WebSocket tickets, rate-limit counters and presence disappear. The app tolerates this (clients refetch tickets and reconnect; presence rebuilds on the next heartbeat).
- **Neon Free:** 1 GB storage, 100 compute-hours/month, **scales to zero after 5 minutes** (first query after idle takes extra seconds). When the allowance is used up, compute suspends until the next period. Watch the Neon console's usage page.
- Health check uses `/health` (liveness) deliberately, so Render's polling doesn't keep Neon awake. `/health/ready` is for manual checks.
- No uptime guarantees, no backups you can rely on. Free plans can change; re-check Render's and Neon's pricing pages occasionally.
- WebSocket connections also count as traffic, but an idle open socket (15 s pings) will keep the backend awake while a lobby is open.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Backend fails at start: `ValueError … FRONTEND_URL must use https` | `FRONTEND_URL` missing/typo; must be the exact `https://…onrender.com` origin, no trailing path |
| Login works but "403 origin_not_allowed" | `FRONTEND_URL` doesn't exactly match the browser's origin |
| `/health/ready` shows `postgis: missing` | Run `CREATE EXTENSION postgis;` in Neon SQL editor |
| asyncpg error about `sslmode` / `channel_binding` | Config normaliser not deployed; confirm `config.py` is updated |
| `too many connections` on Neon | Lower `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`; make sure only one backend instance runs |
| Frontend loads but API calls 502/timeout right after idle | Backend still waking; wait ~1 minute and retry |
| Lobby shows "reconnecting" forever | Check `NEXT_PUBLIC_WS_URL` (baked at build time) is `wss://<backend-host>`; redeploy frontend after changing it |
| Everyone gets 429 on login | `TRUSTED_PROXY_HOPS` too low (see above) |

## Later (optional)
Sentry, OpenTelemetry and S3 (Stage 6) plug in via new environment variables on the backend service; no architecture change is needed. For S3, use a dedicated IAM user limited to one private bucket and add its keys as `sync: false` variables.
