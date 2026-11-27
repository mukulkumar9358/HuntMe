import logging
import uuid

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import (
    check_rate_limit, client_ip, get_current_user, get_db, get_redis, get_settings_dep, require_csrf,
)
from app.core.errors import AppError
from app.infrastructure import presence
from app.infrastructure.realtime import notify_room_changed
from app.infrastructure.ws_ticket import issue_ticket
from app.models.user import User
from app.repositories.room_repository import RoomRepository
from app.schemas.rooms import (
    InviteOut, JoinRequest, MemberOut, MemberUpdate, RoomCreate, RoomCreated, RoomDetail, TeamAssign,
)
from app.services.room_service import RoomService

logger = logging.getLogger("huntme.rooms")
router = APIRouter(prefix="/rooms", tags=["rooms"])


async def _detail(svc: RoomService, redis: Redis, room_id: uuid.UUID, viewer: User) -> RoomDetail:
    snap = await svc.snapshot(room_id, viewer)
    online = await presence.online_user_ids(redis, room_id, [u.id for _, u in snap.members])
    return svc.build_detail(snap, viewer, online)


@router.post("", response_model=RoomCreated, status_code=201, dependencies=[Depends(require_csrf)])
async def create_room(
    body: RoomCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> RoomCreated:
    await check_rate_limit(
        redis, "room_create", str(user.id), settings.room_create_rate_limit_attempts, settings.room_rate_limit_window_seconds
    )
    svc = RoomService(session, settings)
    room, token, expires = await svc.create_room(user, body)
    return RoomCreated(room=await _detail(svc, redis, room.id, user), invite_token=token, invite_expires_at=expires)


@router.post("/join", response_model=RoomDetail, dependencies=[Depends(require_csrf)])
async def join_room(
    body: JoinRequest,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> RoomDetail:
    # Guessing codes is the attack here: limit per account AND per address.
    limit, window = settings.room_join_rate_limit_attempts, settings.room_rate_limit_window_seconds
    await check_rate_limit(redis, "room_join_user", str(user.id), limit, window)
    await check_rate_limit(redis, "room_join_ip", client_ip(request, settings), limit, window)
    svc = RoomService(session, settings)
    room = await svc.join(user, body.room_code, body.invite_token)
    await notify_room_changed(redis, room.id)
    return await _detail(svc, redis, room.id, user)


@router.post("/{room_id}/ws-ticket", dependencies=[Depends(require_csrf)])
async def issue_socket_ticket(
    room_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> dict[str, object]:
    """Mint a single-use ticket for the lobby WebSocket (direct browser -> API connections)."""
    await check_rate_limit(
        redis, "ws_ticket", f"{user.id}:{client_ip(request, settings)}",
        settings.ws_ticket_rate_limit_attempts, settings.room_rate_limit_window_seconds,
    )
    if await RoomRepository(session).active_member_by_user(room_id, user.id) is None:
        raise AppError(404, "room_not_found", "Room not found.")
    try:
        ticket = await issue_ticket(redis, user.id, room_id, settings.ws_ticket_ttl_seconds)
    except RedisError:
        logger.error("ws_ticket_redis_unavailable")
        raise AppError(503, "realtime_unavailable", "Live updates are temporarily unavailable.") from None
    return {"ticket": ticket, "expires_in": settings.ws_ticket_ttl_seconds}


@router.get("/{room_id}", response_model=RoomDetail)
async def get_room(
    room_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> RoomDetail:
    return await _detail(RoomService(session, settings), redis, room_id, user)


@router.get("/{room_id}/members", response_model=list[MemberOut])
async def list_members(
    room_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> list[MemberOut]:
    return (await _detail(RoomService(session, settings), redis, room_id, user)).members


@router.post("/{room_id}/leave", status_code=204, dependencies=[Depends(require_csrf)])
async def leave_room(
    room_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    await RoomService(session, settings).leave(user, room_id)
    await presence.mark_offline(redis, room_id, user.id)
    await notify_room_changed(redis, room_id, removed_user_id=user.id)
    return Response(status_code=204)


@router.patch("/{room_id}/members/me", response_model=RoomDetail, dependencies=[Depends(require_csrf)])
async def update_my_state(
    room_id: uuid.UUID,
    body: MemberUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> RoomDetail:
    svc = RoomService(session, settings)
    await svc.update_me(user, room_id, body)
    await notify_room_changed(redis, room_id)
    return await _detail(svc, redis, room_id, user)


@router.patch("/{room_id}/members/{member_id}/team", response_model=RoomDetail, dependencies=[Depends(require_csrf)])
async def assign_team(
    room_id: uuid.UUID,
    member_id: uuid.UUID,
    body: TeamAssign,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> RoomDetail:
    svc = RoomService(session, settings)
    await svc.assign_team(user, room_id, member_id, body.team_id)
    await notify_room_changed(redis, room_id)
    return await _detail(svc, redis, room_id, user)


@router.post("/{room_id}/invite", response_model=InviteOut, dependencies=[Depends(require_csrf)])
async def regenerate_invite(
    room_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> InviteOut:
    """Host only. Issues a fresh invite link and revokes the previous one (only a hash is stored)."""
    token, expires = await RoomService(session, settings).regenerate_invite(user, room_id)
    return InviteOut(invite_token=token, invite_expires_at=expires)
