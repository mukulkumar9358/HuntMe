import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, token: RefreshToken) -> None:
        self.session.add(token)

    async def get_by_hash_for_update(self, token_hash: str) -> RefreshToken | None:
        """Row-locks the token so two concurrent refreshes can't both succeed."""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        return (await self.session.execute(stmt)).scalars().first()

    async def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.session.execute(stmt)
