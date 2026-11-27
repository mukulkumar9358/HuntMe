"""Central, validated application configuration.

All tunables are read from environment variables (see ``.env.example``).
Startup fails fast with a clear message when required values are missing or
unsafe for the selected environment.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_MARKERS = ("change-me", "changeme", "replace-me", "replace_me", "your-secret", "dev-only", "example")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_debug: bool = False
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"

    database_url: str
    redis_url: str

    jwt_secret: str = Field(min_length=32)
    jwt_access_token_expire_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=90)
    cookie_domain: str | None = None
    trust_proxy_headers: bool = False
    # Number of trusted reverse proxies appending to X-Forwarded-For (e.g. Next.js = 1, load balancer + Next.js = 2).
    trusted_proxy_hops: int = Field(default=1, ge=1, le=5)

    # Auth rate limits (fixed window, per client IP and per account identifier)
    auth_rate_limit_attempts: int = Field(default=10, ge=1)
    auth_rate_limit_window_seconds: int = Field(default=60, ge=1)

    # Rooms (Stage 2)
    room_rate_limit_window_seconds: int = Field(default=60, ge=1)
    room_create_rate_limit_attempts: int = Field(default=10, ge=1)
    room_join_rate_limit_attempts: int = Field(default=10, ge=1)
    invite_token_ttl_hours: int = Field(default=24, ge=1, le=168)
    presence_ttl_seconds: int = Field(default=40, ge=10, le=300)

    # Map provider (used from Stage 3)
    map_provider: str = "maplibre"
    map_api_key: str = ""

    # Object storage (used from Stage 6)
    aws_region: str = ""
    aws_s3_bucket: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Gameplay defaults (consumed from Stage 4 onward; the backend is the source of truth)
    location_ttl_seconds: int = 30
    location_update_interval_seconds: int = 5
    radar_refresh_interval_seconds: int = 15
    default_hide_duration_seconds: int = 120
    default_hunt_duration_seconds: int = 600
    default_qr_expiry_seconds: int = 60
    photo_max_size_mb: int = 10
    photo_retention_days: int = 30

    @property
    def is_production_like(self) -> bool:
        return self.app_env in {"staging", "production"}

    @property
    def cookie_secure(self) -> bool:
        return self.is_production_like

    @property
    def allowed_origins(self) -> list[str]:
        return [self.frontend_url.rstrip("/")]

    @model_validator(mode="after")
    def _validate_for_environment(self) -> "Settings":
        if self.is_production_like:
            if any(m in self.jwt_secret.lower() for m in _PLACEHOLDER_MARKERS):
                raise ValueError("JWT_SECRET must be set to a real random secret")
            if not self.frontend_url.startswith("https://"):
                raise ValueError("FRONTEND_URL must use https in staging/production")
            if self.app_debug:
                raise ValueError("APP_DEBUG must be false in staging/production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
