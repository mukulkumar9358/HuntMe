"""Room change notifications over Redis Pub/Sub.

Messages are deliberately content-free signals ("something changed, refetch"), so they can never leak
role-restricted data. Clients re-read state through authorised REST endpoints.
"""

import json
import logging
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("huntme.realtime")


def room_channel(room_id: uuid.UUID) -> str:
    return f"room:{room_id}"


async def notify_room_changed(redis: Redis, room_id: uuid.UUID, removed_user_id: uuid.UUID | None = None) -> None:
    payload: dict = {"type": "room:updated", "version": 1}
    if removed_user_id is not None:
        payload["removed_user_id"] = str(removed_user_id)
    try:
        await redis.publish(room_channel(room_id), json.dumps(payload))
    except RedisError:
        # State is already committed; clients also poll as a fallback, so don't fail the request.
        logger.error("room_notify_failed", extra={"room_id": str(room_id)})
