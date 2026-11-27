"""FastAPI dependencies: DB session, Redis, settings, current user, CSRF/origin checks, rate limits."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import constant_time_equals, decode_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

logger = logging.getLogger("huntme.deps")

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    user_id = decode_access_token(token, settings) if token else None
    if user_id is None:
        raise AppError(401, "not_authenticated", "Please log in to continue.")
    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise AppError(401, "not_authenticated", "Please log in to continue.")
    return user


def verify_origin(request: Request, settings: Settings = Depends(get_settings_dep)) -> None:
    """Reject cross-site browser requests: unsafe methods must come from the configured frontend origin.

    Browsers always send ``Origin`` on cross-site POSTs; requests without one (curl, server-to-server)
    aren't CSRF vectors because they can't ride a victim's cookies.
    """
    if request.method not in UNSAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in settings.allowed_origins:
        raise AppError(403, "origin_not_allowed", "Request origin is not allowed.")


def require_csrf(request: Request) -> None:
    """Double-submit check for cookie-authenticated mutations."""
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not constant_time_equals(cookie, header):
        raise AppError(403, "csrf_failed", "Security check failed. Refresh the page and try again.")


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            # Each trusted proxy appends the address it saw, so count from the right. Entries further left
            # are client-supplied and must not be trusted (they would let anyone dodge the rate limit).
            hops = [h.strip() for h in fwd.split(",") if h.strip()]
            if len(hops) >= settings.trusted_proxy_hops:
                return hops[-settings.trusted_proxy_hops]
    return request.client.host if request.client else "unknown"


async def check_rate_limit(redis: Redis, scope: str, key: str, limit: int, window: int) -> None:
    """Fixed-window counter. Fails open (with an error log) if Redis is unavailable."""
    redis_key = f"rl:{scope}:{key}"
    try:
        count = await redis.incr(redis_key)
        if count == 1:
            await redis.expire(redis_key, window)
        if count > limit:
            ttl = await redis.ttl(redis_key)
            retry = str(max(ttl, 1))
            raise AppError(
                429, "rate_limited", "Too many attempts. Please wait and try again.", headers={"Retry-After": retry}
            )
    except RedisError:
        logger.error("rate_limit_redis_unavailable", extra={"scope": scope})


def auth_rate_limit(scope: str) -> Callable[..., Awaitable[None]]:
    async def dep(
        request: Request,
        redis: Redis = Depends(get_redis),
        settings: Settings = Depends(get_settings_dep),
    ) -> None:
        await check_rate_limit(
            redis,
            scope,
            client_ip(request, settings),
            settings.auth_rate_limit_attempts,
            settings.auth_rate_limit_window_seconds,
        )

    return dep
