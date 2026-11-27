"""Authentication use-cases: register, login, refresh rotation, logout.

Business rules live here; routes only translate HTTP <-> these calls.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


@dataclass
class SessionTokens:
    access_token: str
    refresh_token: str
    csrf_token: str


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def invalid_credentials() -> AppError:
    return AppError(401, "invalid_credentials", "Incorrect email/username or password.")


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def register(self, username: str, email: str, password: str) -> User:
        if await self.users.username_exists(username):
            raise AppError(409, "username_taken", "That username is already taken.")
        if await self.users.email_exists(email):
            raise AppError(409, "email_taken", "An account with that email already exists.")
        user = User(username=username, email=email, password_hash=await hash_password(password))
        self.users.add(user)
        try:
            await self.session.commit()
        except IntegrityError:  # concurrent registration won the race
            await self.session.rollback()
            raise AppError(409, "account_exists", "That username or email is already in use.") from None
        return user

    async def authenticate(self, identifier: str, password: str) -> User:
        user = await self.users.get_by_identifier(identifier)
        ok = await verify_password(user.password_hash if user else None, password)
        if not ok or user is None or not user.is_active:
            raise invalid_credentials()
        if needs_rehash(user.password_hash):
            user.password_hash = await hash_password(password)
            await self.session.commit()
        return user

    async def start_session(self, user: User, family_id: uuid.UUID | None = None) -> SessionTokens:
        """Issue an access JWT + a fresh refresh token (new family unless rotating)."""
        raw_refresh = generate_opaque_token()
        self.refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id or uuid.uuid4(),
                token_hash=hash_token(raw_refresh),
                expires_at=datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_token_expire_days),
            )
        )
        await self.session.commit()
        return SessionTokens(
            access_token=create_access_token(user.id, self.settings),
            refresh_token=raw_refresh,
            csrf_token=generate_opaque_token(),
        )

    async def rotate_refresh_token(self, raw_token: str) -> tuple[User, SessionTokens]:
        now = datetime.now(timezone.utc)
        record = await self.refresh_tokens.get_by_hash_for_update(hash_token(raw_token))
        if record is None:
            raise AppError(401, "invalid_refresh_token", "Session expired. Please log in again.")
        if record.revoked_at is not None:
            # Reuse of a rotated/revoked token: assume theft and kill the whole family.
            await self.refresh_tokens.revoke_family(record.family_id, now)
            await self.session.commit()
            raise AppError(401, "invalid_refresh_token", "Session expired. Please log in again.")
        if _utc(record.expires_at) <= now:
            raise AppError(401, "invalid_refresh_token", "Session expired. Please log in again.")
        user = await self.users.get(record.user_id)
        if user is None or not user.is_active:
            raise AppError(401, "invalid_refresh_token", "Session expired. Please log in again.")
        record.revoked_at = now
        tokens = await self.start_session(user, family_id=record.family_id)  # commits both changes
        return user, tokens

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        record = await self.refresh_tokens.get_by_hash_for_update(hash_token(raw_token))
        if record is not None:
            await self.refresh_tokens.revoke_family(record.family_id, datetime.now(timezone.utc))
            await self.session.commit()
