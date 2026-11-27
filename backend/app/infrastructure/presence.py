"""Room presence in Redis: a key per (room, user) that expires unless the socket keeps refreshing it."""

import uuid

from redis.asyncio import Redis


def _key(room_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return f"presence:room:{room_id}:{user_id}"


async def mark_online(redis: Redis, room_id: uuid.UUID, user_id: uuid.UUID, ttl: int) -> bool:
    """Returns True if the user was previously offline (i.e. presence just changed)."""
    previous = await redis.set(_key(room_id, user_id), "1", ex=ttl, get=True)
    return previous is None


async def mark_offline(redis: Redis, room_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await redis.delete(_key(room_id, user_id))


async def online_user_ids(redis: Redis, room_id: uuid.UUID, user_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not user_ids:
        return set()
    values = await redis.mget([_key(room_id, u) for u in user_ids])
    return {u for u, v in zip(user_ids, values) if v is not None}
