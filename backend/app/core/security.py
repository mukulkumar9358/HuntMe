"""Password hashing, JWT access tokens and opaque-token helpers."""

import asyncio
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

_hasher = PasswordHasher()  # Argon2id with library defaults
# Verified against when a user is not found, so response time doesn't reveal account existence.
_DUMMY_HASH = _hasher.hash("huntme-dummy-password")

ACCESS_TOKEN_TYPE = "access"


def _hash_sync(password: str) -> str:
    return _hasher.hash(password)


def _verify_sync(hashed: str, password: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash_sync, password)


async def verify_password(hashed: str | None, password: str) -> bool:
    """Always performs a verification, even for unknown users, to keep timing uniform."""
    ok = await asyncio.to_thread(_verify_sync, hashed or _DUMMY_HASH, password)
    return ok and hashed is not None


def needs_rehash(hashed: str) -> bool:
    return _hasher.check_needs_rehash(hashed)


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> uuid.UUID | None:
    try:
        claims = jwt.decode(
            token, settings.jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "type"]}
        )
        if claims.get("type") != ACCESS_TOKEN_TYPE:
            return None
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


def generate_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """SHA-256 hex digest. Opaque tokens are high-entropy, so a fast hash is appropriate."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
