import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import GameRoom, RoomMember, Team
from app.models.user import User


class RoomRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- rooms
    def add(self, obj: GameRoom | Team | RoomMember) -> None:
        self.session.add(obj)

    async def get_room(self, room_id: uuid.UUID) -> GameRoom | None:
        return await self.session.get(GameRoom, room_id)

    async def get_room_for_update(self, room_id: uuid.UUID) -> GameRoom | None:
        """Row lock: serialises joins/leaves so capacity and host hand-over can't race."""
        stmt = (
            select(GameRoom).where(GameRoom.id == room_id).with_for_update().execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_by_code(self, code: str) -> GameRoom | None:
        return (await self.session.execute(select(GameRoom).where(GameRoom.room_code == code))).scalars().first()

    async def get_by_invite_hash(self, token_hash: str) -> GameRoom | None:
        stmt = select(GameRoom).where(GameRoom.invite_token_hash == token_hash)
        return (await self.session.execute(stmt)).scalars().first()

    # --- teams
    async def teams(self, room_id: uuid.UUID) -> list[Team]:
        stmt = select(Team).where(Team.room_id == room_id).order_by(Team.position)
        return list((await self.session.execute(stmt)).scalars())

    # --- members
    async def active_members(self, room_id: uuid.UUID) -> list[tuple[RoomMember, User]]:
        stmt = (
            select(RoomMember, User)
            .join(User, User.id == RoomMember.user_id)
            .where(RoomMember.room_id == room_id, RoomMember.left_at.is_(None))
            .order_by(RoomMember.joined_at, RoomMember.id)
        )
        return [(m, u) for m, u in (await self.session.execute(stmt)).all()]

    async def active_member_by_user(self, room_id: uuid.UUID, user_id: uuid.UUID) -> RoomMember | None:
        stmt = select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user_id, RoomMember.left_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def active_member_by_id(self, room_id: uuid.UUID, member_id: uuid.UUID) -> RoomMember | None:
        stmt = select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.id == member_id, RoomMember.left_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def count_active(self, room_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.left_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def team_sizes(self, room_id: uuid.UUID) -> list[tuple[uuid.UUID, int]]:
        """(team_id, active member count) ordered by team position."""
        stmt = (
            select(Team.id, func.count(RoomMember.id))
            .outerjoin(RoomMember, (RoomMember.team_id == Team.id) & RoomMember.left_at.is_(None))
            .where(Team.room_id == room_id)
            .group_by(Team.id, Team.position)
            .order_by(Team.position)
        )
        return [(tid, n) for tid, n in (await self.session.execute(stmt)).all()]

    async def next_host_candidate(self, room_id: uuid.UUID, excluding_user_id: uuid.UUID) -> RoomMember | None:
        stmt = (
            select(RoomMember)
            .where(RoomMember.room_id == room_id, RoomMember.left_at.is_(None), RoomMember.user_id != excluding_user_id)
            .order_by(RoomMember.joined_at, RoomMember.id)
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    @staticmethod
    def now() -> datetime:
        from datetime import timezone
        return datetime.now(timezone.utc)
