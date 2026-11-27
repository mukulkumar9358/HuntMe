"""Lobby WebSocket: /ws/rooms/{room_id}.

Auth is either a single-use ticket (production, cross-host) or the HttpOnly access-token cookie (same host), checked
at the handshake together with the Origin header and active room membership. The socket only carries content-free "room:updated" signals plus presence
heartbeats; clients refetch real data over authorised REST.
"""

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket
from redis.exceptions import RedisError

from app.core.dependencies import ACCESS_COOKIE
from app.core.security import decode_access_token
from app.infrastructure import presence
from app.infrastructure.realtime import notify_room_changed, room_channel
from app.infrastructure.ws_ticket import SUBPROTOCOL, consume_ticket, ticket_from_subprotocols
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger("huntme.ws")
router = APIRouter()

MAX_MESSAGE_CHARS = 1024
MAX_MESSAGES_PER_10S = 30

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_REMOVED = 4000


@router.websocket("/ws/rooms/{room_id}")
async def lobby_socket(websocket: WebSocket, room_id: uuid.UUID) -> None:
    app = websocket.app
    settings = app.state.settings
    redis = app.state.redis

    origin = websocket.headers.get("origin")
    if origin and origin.rstrip("/") not in settings.allowed_origins:
        await websocket.close(code=CLOSE_FORBIDDEN)
        return

    # Production: the browser connects straight to this host, so it presents a single-use ticket (minted via the
    # same-origin REST API) in the Sec-WebSocket-Protocol header. Local Docker (same host) still works with the
    # access-token cookie. Either way the user must be an active member of this room.
    subprotocol: str | None = None
    ticket = ticket_from_subprotocols(websocket.scope.get("subprotocols", []))
    if ticket is not None:
        subprotocol = SUBPROTOCOL
        try:
            consumed = await consume_ticket(redis, ticket)
        except RedisError:
            logger.error("ws_ticket_redis_unavailable")
            await websocket.close(code=1011)
            return
        if consumed is None or consumed[1] != room_id:
            await websocket.close(code=CLOSE_UNAUTHORIZED)
            return
        user_id: uuid.UUID | None = consumed[0]
    else:
        token = websocket.cookies.get(ACCESS_COOKIE)
        user_id = decode_access_token(token, settings) if token else None
    if user_id is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    async with app.state.sessionmaker() as session:  # short-lived: don't hold a DB connection for the socket's life
        user = await UserRepository(session).get(user_id)
        member = await RoomRepository(session).active_member_by_user(room_id, user_id) if user and user.is_active else None
    if user is None or not user.is_active:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return
    if member is None:
        await websocket.close(code=CLOSE_FORBIDDEN)
        return

    await websocket.accept(subprotocol=subprotocol)
    pubsub = redis.pubsub()
    ttl = settings.presence_ttl_seconds
    try:
        await pubsub.subscribe(room_channel(room_id))
        if await presence.mark_online(redis, room_id, user_id, ttl):
            await notify_room_changed(redis, room_id)
    except RedisError:
        logger.error("ws_redis_unavailable")
        await websocket.close(code=1011)
        return

    stop = asyncio.Event()

    async def forward() -> None:
        while not stop.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            raw = message["data"]
            await websocket.send_text(raw)
            try:
                if json.loads(raw).get("removed_user_id") == str(user_id):
                    await websocket.close(code=CLOSE_REMOVED)
                    return
            except (ValueError, AttributeError):
                pass

    async def receive() -> None:
        window_start, count = time.monotonic(), 0
        while True:
            text = await websocket.receive_text()
            now = time.monotonic()
            if now - window_start > 10:
                window_start, count = now, 0
            count += 1
            if len(text) > MAX_MESSAGE_CHARS or count > MAX_MESSAGES_PER_10S:
                await websocket.close(code=1008)
                return
            try:
                kind = json.loads(text).get("type")
            except (ValueError, AttributeError):
                continue
            if kind == "ping":
                await presence.mark_online(redis, room_id, user_id, ttl)
                await websocket.send_text(json.dumps({"type": "pong", "version": 1}))

    async def cleanup() -> None:
        try:
            await presence.mark_offline(redis, room_id, user_id)
            await notify_room_changed(redis, room_id)
        except RedisError:
            logger.error("ws_cleanup_failed")

    tasks = [asyncio.create_task(forward()), asyncio.create_task(receive())]
    cleanup_task: asyncio.Future[None] | None = None
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        # Start presence cleanup FIRST, as its own task: if this handler is cancelled (server shutdown, or an
        # ASGI server tearing down the connection) at any await below, the cleanup still runs to completion.
        cleanup_task = asyncio.ensure_future(cleanup())
        # Cancelling a task parked inside a Redis read doesn't reliably wake it, so stop it explicitly:
        # flag it, close the pubsub connection under it, and bound how long we wait.
        stop.set()
        for t in tasks:
            t.cancel()
        try:
            await pubsub.aclose()
        except Exception:  # noqa: BLE001 - best effort; the connection is being discarded anyway
            pass
        await asyncio.wait(tasks, timeout=3)
        for t in tasks:  # mark exceptions (e.g. the client's normal disconnect) as retrieved
            if t.done() and not t.cancelled():
                t.exception()
        await asyncio.shield(cleanup_task)
