import os
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from contextlib import AsyncExitStack

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://huntme:huntme_dev_pw@localhost:5432/huntme_test"
)
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")
ORIGIN = "http://localhost:3000"


def make_settings(**overrides) -> Settings:
    base = dict(
        app_env="test",
        database_url=TEST_DATABASE_URL,
        redis_url=TEST_REDIS_URL,
        jwt_secret="test-secret-test-secret-test-secret-123456",
        auth_rate_limit_attempts=1000,
        room_create_rate_limit_attempts=1000,
        room_join_rate_limit_attempts=1000,
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Build the test schema from the real Alembic migrations (downgrade -> upgrade)."""
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL, "REDIS_URL": TEST_REDIS_URL,
           "JWT_SECRET": "test-secret-test-secret-test-secret-123456", "APP_ENV": "test"}
    for target in (["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run([sys.executable, "-m", "alembic", *target], cwd=BACKEND_DIR, env=env, check=True)


@pytest_asyncio.fixture(autouse=True)
async def clean_state() -> AsyncIterator[None]:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, refresh_tokens, game_rooms, teams, room_members CASCADE"))
    await engine.dispose()
    redis = Redis.from_url(TEST_REDIS_URL)
    await redis.flushdb()
    await redis.aclose()
    yield


@asynccontextmanager
async def make_client(**overrides) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_settings(**overrides))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", headers={"Origin": ORIGIN}
        ) as client:
            client.app = app  # type: ignore[attr-defined]
            yield client


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with make_client() as c:
        yield c


VALID_USER = {"username": "Mukul_01", "email": "Mukul@Example.com", "password": "correct-horse-battery"}


async def register(client: httpx.AsyncClient, **overrides) -> httpx.Response:
    return await client.post("/api/v1/auth/register", json={**VALID_USER, **overrides})


def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("csrf_token") or ""}


@pytest_asyncio.fixture
async def players():
    """Factory for independent logged-in clients (separate cookie jars), one per player."""
    stack = AsyncExitStack()

    async def make(name: str, **overrides) -> httpx.AsyncClient:
        c = await stack.enter_async_context(make_client(**overrides))
        r = await register(c, username=name, email=f"{name.lower()}@example.com")
        assert r.status_code == 201, r.text
        return c

    yield make
    await stack.aclose()


async def post(c: httpx.AsyncClient, url: str, json=None) -> httpx.Response:
    return await c.post(url, json=json, headers=csrf_headers(c))


async def patch(c: httpx.AsyncClient, url: str, json=None) -> httpx.Response:
    return await c.patch(url, json=json, headers=csrf_headers(c))


async def sql(statement: str):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(text(statement))
        rows = result.all() if result.returns_rows else []
    await engine.dispose()
    return rows
