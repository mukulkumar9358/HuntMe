import pytest
from pydantic import ValidationError

from tests.conftest import make_client, make_settings


async def test_liveness(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_readiness_checks_db_postgis_and_redis(client):
    r = await client.get("/health/ready")
    body = r.json()
    assert r.status_code == 200, body
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["postgis"].startswith("ok")
    assert body["checks"]["redis"] == "ok"


async def test_readiness_reports_503_when_redis_down():
    async with make_client(redis_url="redis://localhost:6399/0") as c:
        r = await c.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["redis"] == "error"
    assert r.json()["checks"]["database"] == "ok"


def test_short_jwt_secret_rejected():
    with pytest.raises(ValidationError):
        make_settings(jwt_secret="too-short")


def test_production_requires_https_and_real_secret():
    with pytest.raises(ValidationError):
        make_settings(app_env="production", frontend_url="http://example.com")
    with pytest.raises(ValidationError):
        make_settings(app_env="production", frontend_url="https://example.com",
                      jwt_secret="change-me" * 5, app_debug=False)
    ok = make_settings(app_env="production", frontend_url="https://example.com",
                       jwt_secret="k9Qv3xT7mZp2LwR8nB5cYd1HfS6aGjE4uXo0")
    assert ok.cookie_secure is True


def test_missing_required_env_fails_fast(monkeypatch):
    from app.core.config import Settings
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
