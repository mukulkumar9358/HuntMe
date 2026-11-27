from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cookies import clear_auth_cookies, set_auth_cookies
from app.core.config import Settings
from app.core.dependencies import (
    REFRESH_COOKIE,
    auth_rate_limit,
    check_rate_limit,
    get_db,
    get_redis,
    get_settings_dep,
    require_csrf,
)
from app.core.errors import AppError
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _service(session: AsyncSession, settings: Settings) -> AuthService:
    return AuthService(session, settings)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    dependencies=[Depends(auth_rate_limit("register"))],
)
async def register(
    body: RegisterRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AuthResponse:
    svc = _service(session, settings)
    user = await svc.register(body.username, body.email, body.password)
    set_auth_cookies(response, await svc.start_session(user), settings)
    return AuthResponse(user=user)  # type: ignore[arg-type]


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(auth_rate_limit("login"))])
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings_dep),
) -> AuthResponse:
    # Per-account limit on top of the per-IP one, to slow distributed guessing of one account.
    await check_rate_limit(
        redis,
        "login_account",
        body.identifier.strip().lower(),
        settings.auth_rate_limit_attempts,
        settings.auth_rate_limit_window_seconds,
    )
    svc = _service(session, settings)
    user = await svc.authenticate(body.identifier, body.password)
    set_auth_cookies(response, await svc.start_session(user), settings)
    return AuthResponse(user=user)  # type: ignore[arg-type]


@router.post("/refresh", response_model=AuthResponse, dependencies=[Depends(require_csrf)])
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AuthResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise AppError(401, "invalid_refresh_token", "Session expired. Please log in again.")
    svc = _service(session, settings)
    user, tokens = await svc.rotate_refresh_token(raw)
    set_auth_cookies(response, tokens, settings)
    return AuthResponse(user=user)  # type: ignore[arg-type]


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    await _service(session, settings).logout(request.cookies.get(REFRESH_COOKIE))
    clear_auth_cookies(response, settings)
    response.status_code = 204
    return response
