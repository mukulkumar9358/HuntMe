import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_identifier(self, identifier: str) -> User | None:
        ident = identifier.strip().lower()
        stmt = select(User).where(or_(User.email == ident, func.lower(User.username) == ident))
        return (await self.session.execute(stmt)).scalars().first()

    async def email_exists(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email.lower())
        return (await self.session.execute(stmt)).first() is not None

    async def username_exists(self, username: str) -> bool:
        stmt = select(User.id).where(func.lower(User.username) == username.lower())
        return (await self.session.execute(stmt)).first() is not None

    def add(self, user: User) -> None:
        self.session.add(user)
