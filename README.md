# HuntMe

**Hide. Hunt. Prove it.** A real-world, location-based multiplayer hide-and-seek game (mobile-first PWA).

Status: **Stage 2 (rooms and teams) complete.** Maps/arena, the game engine, radar, discovery and the rest follow the staged roadmap.

| Layer | Tech |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS 4, TanStack Query, react-hook-form + Zod |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Data | PostgreSQL 16 + PostGIS 3.4, Redis 7 |
| Evidence storage (Stage 6) | Private AWS S3 |

## Quick start (Docker)

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD (letters/digits only) and JWT_SECRET:
python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up --build
```

Open http://localhost:3000. The API is on http://localhost:8000 (docs at `/docs` outside production).
Postgres and Redis are **not** published to the host. Use `docker compose exec huntme-db psql -U huntme`.

## Local development (no Docker)

Requires Python 3.12+, Node 22+, PostgreSQL with PostGIS, and Redis.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env        # set DATABASE_URL, REDIS_URL, JWT_SECRET
alembic upgrade head
uvicorn app.main:get_app --factory --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
BACKEND_INTERNAL_URL=http://localhost:8000 npm run dev
```

## How the pieces connect

The browser only talks to the frontend origin. Next.js proxies `/api/v1/*` to FastAPI (`next.config.ts`), so auth
cookies are first-party: no CORS and `SameSite=Lax` works. `BACKEND_INTERNAL_URL` is **baked in at build time**
(it is a Docker build arg). WebSockets (Stage 4) will connect to the backend directly, so production should put
both behind one domain or share a parent cookie domain (`COOKIE_DOMAIN`).

## Rooms and lobby (Stage 2)

- Create a room (`/create-room`), share its 8-character code or an invite link, and manage teams in the lobby (`/lobby/<id>`).
- Limits and defaults (players, hiding/hunting time, clue interval) are enforced by the server and served from `GET /api/v1/game-config`; the UI renders from that.
- Two fixed teams, Red and Blue. Joiners are auto-balanced (or left unassigned if the host chose manual teams). Only the host can move players; roles (hider/seeker) are assigned per match in a later stage, not per team.
- Joining: `POST /rooms/join` with a room code **or** an invite token. Codes use an unambiguous alphabet and joins are rate limited per account and per IP. Unknown codes, wrong/expired/revoked invites, and "not a member" all return the same 404 so rooms can't be probed.
- Invite links expire (24 h by default). Only a hash is stored, so the host's tab remembers the link it created; "Copy invite link" on another device issues a new one and **revokes the old one**.
- Capacity is enforced under a row lock, so concurrent joins can't overfill a room. Re-joining is idempotent. If the host leaves, the longest-standing member becomes host; if the room empties it is cancelled.
- Players must accept the safety rules (stored per player) before they can mark themselves ready. Location/camera permission indicators are informational and reported by the client.
- "Start game" is intentionally disabled in this stage. The server returns the reasons (`start_blockers`), including `arena_missing`, which Stage 3 will clear.

Endpoints (`/api/v1`): `POST /rooms`, `POST /rooms/join`, `GET /rooms/{id}`, `GET /rooms/{id}/members`, `POST /rooms/{id}/leave`,
`PATCH /rooms/{id}/members/me`, `PATCH /rooms/{id}/members/{member_id}/team`, `POST /rooms/{id}/invite`, `GET /game-config`.
All mutating calls need the CSRF header; non-members get 404 for any room.

### Live lobby (WebSocket)

`/ws/rooms/{room_id}` authenticates with the same cookie, checks the `Origin` header and active membership, then pushes content-free
`{"type":"room:updated"}` signals over Redis Pub/Sub. Clients refetch real data over REST, so nothing role-restricted ever travels on the socket.
It also carries presence heartbeats (`ping`/`pong`, 40 s TTL in Redis). Leaving the room closes your socket (code 4000). If the socket is down the UI polls every 5 s.
The browser connects to the API directly (Next.js rewrites can't proxy WebSockets reliably): set `NEXT_PUBLIC_WS_URL` at build time
(`ws://localhost:8000` locally; `wss://api.example.com` in production, with `COOKIE_DOMAIN` set so the auth cookie reaches that host).

## Authentication

- Argon2id password hashes; access JWT (15 min) + rotating refresh token (30 days), all in `HttpOnly` cookies.
- Refresh tokens are stored hashed. Re-using a rotated token revokes the whole login family.
- CSRF: double-submit token (`csrf_token` cookie echoed as `X-CSRF-Token`) for refresh/logout, plus an `Origin` check on every mutating `/api/v1` request.
- Login/register are rate limited per IP, and login also per account (Redis, fixed window). If Redis is down the limiter fails open and logs an error.
- Behind a proxy set `TRUST_PROXY_HEADERS=true` and `TRUSTED_PROXY_HOPS` to the number of trusted proxies. The client IP is read from the right of `X-Forwarded-For`.

Endpoints (`/api/v1`): `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`; `GET /users/me`.
Health (unversioned): `GET /health` (liveness), `GET /health/ready` (Postgres, PostGIS, Redis).
Errors always look like `{"error": {"code", "message", "details?"}}`.

## Database

```bash
cd backend
alembic upgrade head      # apply migrations (also enables the PostGIS extension)
alembic check             # fails if models and migrations have drifted
alembic revision --autogenerate -m "describe change"
```

## Tests

```bash
# Backend: needs real Postgres+PostGIS and Redis (database `huntme_test`, Redis db 1)
cd backend && pytest
# override with TEST_DATABASE_URL / TEST_REDIS_URL

# Frontend
cd frontend && npm test && npm run typecheck && npm run lint && npm run build
```

The backend test session rebuilds the schema from the real migrations (downgrade, then upgrade), and a test fails if models drift from migrations.

## Configuration

All settings are environment variables (see `.env.example`). The backend refuses to start if required values are
missing, `JWT_SECRET` is shorter than 32 characters, or, in staging/production, the secret looks like a placeholder,
`FRONTEND_URL` isn't https, or debug is on.

## Troubleshooting

- **`JWT_SECRET` / `POSTGRES_PASSWORD` error from compose**: set them in `.env`.
- **403 `origin_not_allowed`**: the browser's origin must equal `FRONTEND_URL`.
- **Everyone hits the rate limit at once**: the backend sees the proxy's IP. Set `TRUST_PROXY_HEADERS=true` and the right `TRUSTED_PROXY_HOPS`.
- **Lobby says "Reconnecting…" forever**: the browser can't reach the API's WebSocket. Check `NEXT_PUBLIC_WS_URL` (build-time) and that the cookie is sent to that host.
- **Frontend can't reach the API in Docker**: rebuild after changing `BACKEND_INTERNAL_URL` (`docker compose build huntme-frontend`).

## Safety note

HuntMe is played in the real world. Only play where you have permission; stay off roads, railway tracks, rooftops and
construction sites. Before any public launch, get a privacy/legal review for location, camera and personal data in your target markets.
