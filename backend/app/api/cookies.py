from fastapi import Response

from app.core.config import Settings
from app.core.dependencies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from app.services.auth_service import SessionTokens

AUTH_PATH = "/api/v1/auth"


def set_auth_cookies(response: Response, tokens: SessionTokens, settings: Settings) -> None:
    common = {"secure": settings.cookie_secure, "samesite": "lax", "domain": settings.cookie_domain}
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        httponly=True,
        path="/",
        **common,
    )
    # Refresh token is only ever sent to the auth endpoints.
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        path=AUTH_PATH,
        **common,
    )
    # Readable by JS on purpose: the frontend echoes it in X-CSRF-Token (double-submit).
    response.set_cookie(
        CSRF_COOKIE,
        tokens.csrf_token,
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=False,
        path="/",
        **common,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    domain = settings.cookie_domain
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_COOKIE, path=AUTH_PATH, domain=domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=domain)
