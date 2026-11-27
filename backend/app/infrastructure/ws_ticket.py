"""Short-lived, single-use WebSocket tickets stored in Redis / Key Value.

Why: in production the browser talks to the API through the frontend's same-origin proxy (cookies belong to the
frontend host) but opens WebSockets directly against the backend host, where those cookies are not sent. An
authenticated REST call mints a ticket; the socket handshake presents it exactly once.

Security properties:
* 256-bit random value; only its SHA-256 is stored, so a Redis dump never contains a usable ticket.
* Bound to one user AND one room.
* ``GETDEL`` consumes it atomically: a second use (or a race between two sockets) finds nothing.
* Short TTL. Redis data loss simply invalidates outstanding tickets; the client fetches a new one.
* Never placed in a URL (it travels in the ``Sec-WebSocket-Protocol`` header), so access logs can't capture it.
"""

import uuid

from redis.asyncio import Redis

from app.core.security import generate_opaque_token, hash_token

SUBPROTOCOL = "huntme.ticket"


def _key(ticket: str) -> str:
    return f"wst:{hash_token(ticket)}"


async def issue_ticket(redis: Redis, user_id: uuid.UUID, room_id: uuid.UUID, ttl_seconds: int) -> str:
    ticket = generate_opaque_token(32)
    await redis.set(_key(ticket), f"{user_id}:{room_id}", ex=ttl_seconds)
    return ticket


async def consume_ticket(redis: Redis, ticket: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    """Atomically validate and burn a ticket. Returns (user_id, room_id) or None if unknown/expired/used."""
    if not ticket or len(ticket) > 128:
        return None
    raw = await redis.getdel(_key(ticket))
    if raw is None:
        return None
    try:
        user_part, room_part = raw.split(":", 1)
        return uuid.UUID(user_part), uuid.UUID(room_part)
    except ValueError:
        return None


def ticket_from_subprotocols(offered: list[str]) -> str | None:
    """Client offers ``["huntme.ticket", "<ticket>"]``; return the ticket if that shape is present."""
    if len(offered) == 2 and offered[0] == SUBPROTOCOL:
        return offered[1]
    return None
