"""Room use-cases: create, join, leave, per-member state, invites, and the lobby view.

All state-changing methods commit before returning. Capacity, host hand-over and team moves happen under a
row lock on the room so concurrent requests can't over-fill or corrupt a lobby.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.game_rules import TEAM_DEFS
from app.core.security import generate_opaque_token, hash_token
from app.models.room import GameRoom, RoomMember, Team
from app.models.user import User
from app.repositories.room_repository import RoomRepository
from app.schemas.rooms import (
    BlockerOut, MemberOut, MemberUpdate, RoomCreate, RoomDetail, TeamOut,
)
from app.services.lobby_rules import (
    MemberView, TeamView, generate_room_code, normalize_room_code, pick_team, start_blockers, teams_unbalanced,
)


def room_not_found() -> AppError:
    # One answer for "no such room", "wrong code", "expired invite" and "not a member": nothing to enumerate.
    return AppError(404, "room_not_found", "We couldn't find that room.")


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class RoomSnapshot:
    room: GameRoom
    teams: list[Team]
    members: list[tuple[RoomMember, User]]


class RoomService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repo = RoomRepository(session)

    # ------------------------------------------------------------------ create
    async def create_room(self, host: User, data: RoomCreate) -> tuple[GameRoom, str, datetime]:
        raw_token = generate_opaque_token()
        expires = datetime.now(timezone.utc) + timedelta(hours=self.settings.invite_token_ttl_hours)
        fields = dict(
            room_name=data.room_name,
            max_players=data.max_players,
            hide_duration_seconds=data.hide_duration_seconds or self.settings.default_hide_duration_seconds,
            hunt_duration_seconds=data.hunt_duration_seconds or self.settings.default_hunt_duration_seconds,
            clue_interval_seconds=data.clue_interval_seconds or 120,
            shrinking_zone_enabled=data.shrinking_zone_enabled,
            join_policy=data.join_policy,
            auto_balance_teams=data.auto_balance_teams,
            host_user_id=host.id,
            invite_token_hash=hash_token(raw_token),
            invite_expires_at=expires,
        )
        room: GameRoom | None = None
        for _ in range(5):  # a code collision is astronomically unlikely, but the unique index is the real guard
            candidate = GameRoom(room_code=generate_room_code(), **fields)
            try:
                async with self.session.begin_nested():
                    self.repo.add(candidate)
                    await self.session.flush()
                room = candidate
                break
            except IntegrityError:
                continue
        if room is None:
            raise AppError(503, "room_code_unavailable", "Couldn't create a room right now. Try again.")

        teams = [Team(id=uuid.uuid4(), room_id=room.id, name=n, color=c, position=i) for i, (n, c) in enumerate(TEAM_DEFS)]
        for t in teams:
            self.repo.add(t)
        await self.session.flush()
        self.repo.add(RoomMember(room_id=room.id, user_id=host.id, team_id=teams[0].id))
        await self.session.commit()
        return room, raw_token, expires

    # -------------------------------------------------------------------- join
    async def join(self, user: User, room_code: str | None, invite_token: str | None) -> GameRoom:
        now = datetime.now(timezone.utc)
        if invite_token:
            room = await self.repo.get_by_invite_hash(hash_token(invite_token))
            if room is None or room.invite_expires_at is None or _utc(room.invite_expires_at) <= now:
                raise room_not_found()
        else:
            room = await self.repo.get_by_code(normalize_room_code(room_code or ""))
            if room is None or room.join_policy != "CODE":
                raise room_not_found()

        locked = await self.repo.get_room_for_update(room.id)
        if locked is None or locked.status in ("FINISHED", "CANCELLED"):
            raise room_not_found()
        room = locked

        if await self.repo.active_member_by_user(room.id, user.id):
            return room  # joining twice is a no-op, never a duplicate row
        if room.status != "WAITING":
            raise AppError(409, "room_in_progress", "This game has already started.")
        if await self.repo.count_active(room.id) >= room.max_players:
            raise AppError(409, "room_full", "This room is full.")

        team_id = pick_team(await self.repo.team_sizes(room.id)) if room.auto_balance_teams else None
        self.repo.add(RoomMember(room_id=room.id, user_id=user.id, team_id=team_id))
        await self.session.commit()
        return room

    # ------------------------------------------------------------------- leave
    async def leave(self, user: User, room_id: uuid.UUID) -> uuid.UUID:
        room = await self.repo.get_room_for_update(room_id)
        member = await self.repo.active_member_by_user(room_id, user.id) if room else None
        if room is None or member is None:
            raise room_not_found()
        member.left_at = datetime.now(timezone.utc)
        member.team_id = None
        member.is_ready = False
        if room.host_user_id == user.id:
            successor = await self.repo.next_host_candidate(room.id, user.id)
            if successor:
                room.host_user_id = successor.user_id
            else:
                room.status = "CANCELLED"
                room.invite_token_hash = None
        await self.session.commit()
        return room.id

    # ---------------------------------------------------------- member state
    async def update_me(self, user: User, room_id: uuid.UUID, data: MemberUpdate) -> None:
        room = await self.repo.get_room_for_update(room_id)
        member = await self.repo.active_member_by_user(room_id, user.id) if room else None
        if room is None or member is None:
            raise room_not_found()
        changes = data.model_dump(exclude_unset=True, exclude_none=True)

        if "location_permission" in changes:
            member.location_permission = changes["location_permission"]
        if "camera_permission" in changes:
            member.camera_permission = changes["camera_permission"]

        gameplay_change = "safety_acknowledged" in changes or "is_ready" in changes
        if gameplay_change and room.status != "WAITING":
            raise AppError(409, "room_not_editable", "The game has already started.")

        if "safety_acknowledged" in changes:
            if changes["safety_acknowledged"]:
                member.safety_acknowledged_at = member.safety_acknowledged_at or datetime.now(timezone.utc)
            else:
                member.safety_acknowledged_at = None
                member.is_ready = False
        if "is_ready" in changes:
            if changes["is_ready"]:
                if member.team_id is None:
                    raise AppError(409, "not_on_team", "Join a team before getting ready.")
                if member.safety_acknowledged_at is None:
                    raise AppError(409, "safety_not_acknowledged", "Read and accept the safety rules first.")
            member.is_ready = changes["is_ready"]
        await self.session.commit()

    # ------------------------------------------------------------------- teams
    async def assign_team(self, actor: User, room_id: uuid.UUID, member_id: uuid.UUID, team_id: uuid.UUID) -> None:
        room = await self.repo.get_room_for_update(room_id)
        if room is None or await self.repo.active_member_by_user(room_id, actor.id) is None:
            raise room_not_found()
        if room.host_user_id != actor.id:
            raise AppError(403, "not_host", "Only the host can change teams.")
        if room.status != "WAITING":
            raise AppError(409, "room_not_editable", "Teams are locked once the game has started.")
        target = await self.repo.active_member_by_id(room_id, member_id)
        if target is None:
            raise AppError(404, "member_not_found", "That player isn't in this room.")
        if team_id not in {t.id for t in await self.repo.teams(room_id)}:
            raise AppError(404, "team_not_found", "That team doesn't exist in this room.")
        target.team_id = team_id
        await self.session.commit()

    # ------------------------------------------------------------------ invite
    async def regenerate_invite(self, actor: User, room_id: uuid.UUID) -> tuple[str, datetime]:
        room = await self.repo.get_room_for_update(room_id)
        if room is None or await self.repo.active_member_by_user(room_id, actor.id) is None:
            raise room_not_found()
        if room.host_user_id != actor.id:
            raise AppError(403, "not_host", "Only the host can create invite links.")
        if room.status != "WAITING":
            raise AppError(409, "room_not_editable", "The game has already started.")
        raw = generate_opaque_token()
        room.invite_token_hash = hash_token(raw)
        room.invite_expires_at = datetime.now(timezone.utc) + timedelta(hours=self.settings.invite_token_ttl_hours)
        await self.session.commit()
        return raw, room.invite_expires_at

    # -------------------------------------------------------------------- view
    async def snapshot(self, room_id: uuid.UUID, viewer: User) -> RoomSnapshot:
        """Everything the lobby shows. 404s for non-members so room ids can't be probed."""
        room = await self.repo.get_room(room_id)
        if room is None or await self.repo.active_member_by_user(room_id, viewer.id) is None:
            raise room_not_found()
        return RoomSnapshot(room, await self.repo.teams(room_id), await self.repo.active_members(room_id))

    @staticmethod
    def build_detail(snap: RoomSnapshot, viewer: User, online: set[uuid.UUID]) -> RoomDetail:
        room = snap.room
        members_out = [
            MemberOut(
                id=m.id, user_id=u.id, username=u.username, avatar_url=u.avatar_url, team_id=m.team_id,
                is_ready=m.is_ready, is_host=u.id == room.host_user_id, online=u.id in online,
                safety_acknowledged=m.safety_acknowledged_at is not None,
                location_permission=m.location_permission, camera_permission=m.camera_permission,
                joined_at=m.joined_at,
            )
            for m, u in snap.members
        ]
        blockers = start_blockers(
            members=[MemberView(m.user_id, m.team_id, m.is_ready, m.safety_acknowledged_at is not None) for m, _ in snap.members],
            teams=[TeamView(t.id, t.name) for t in snap.teams],
            host_user_id=room.host_user_id,
            has_arena=False,  # arenas arrive in Stage 3; until then a match can't start
        )
        sizes = [sum(1 for m, _ in snap.members if m.team_id == t.id) for t in snap.teams]
        me = next(m.id for m, u in snap.members if u.id == viewer.id)
        return RoomDetail(
            id=room.id, room_code=room.room_code, room_name=room.room_name, status=room.status,
            host_user_id=room.host_user_id, max_players=room.max_players, member_count=len(snap.members),
            join_policy=room.join_policy, auto_balance_teams=room.auto_balance_teams,
            hide_duration_seconds=room.hide_duration_seconds, hunt_duration_seconds=room.hunt_duration_seconds,
            clue_interval_seconds=room.clue_interval_seconds, shrinking_zone_enabled=room.shrinking_zone_enabled,
            created_at=room.created_at,
            teams=[TeamOut(id=t.id, name=t.name, color=t.color, position=t.position) for t in snap.teams],
            members=members_out, me=me,
            start_blockers=[BlockerOut(code=b.code, detail=b.detail) for b in blockers],
            teams_unbalanced=teams_unbalanced(sizes),
        )
