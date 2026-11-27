import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.refresh_token import RefreshToken
from tests.conftest import TEST_DATABASE_URL, VALID_USER, csrf_headers, make_client, make_settings, register


async def _db_rows(sql: str):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql))).all()
    await engine.dispose()
    return rows


async def test_register_sets_secure_cookies_and_hashes_password(client):
    r = await register(client)
    assert r.status_code == 201, r.text
    user = r.json()["user"]
    assert user["username"] == "Mukul_01" and user["email"] == "mukul@example.com"
    assert "password" not in r.text and "password_hash" not in r.text

    set_cookie = r.headers.get_list("set-cookie")
    access = next(c for c in set_cookie if c.startswith("access_token="))
    refresh = next(c for c in set_cookie if c.startswith("refresh_token="))
    csrf = next(c for c in set_cookie if c.startswith("csrf_token="))
    assert "HttpOnly" in access and "SameSite=lax" in access
    assert "HttpOnly" in refresh and "Path=/api/v1/auth" in refresh
    assert "HttpOnly" not in csrf  # readable by JS for double-submit

    (row,) = await _db_rows("SELECT password_hash FROM users")
    assert row[0].startswith("$argon2id$") and "correct-horse" not in row[0]


async def test_me_after_register_and_unauthenticated(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    await register(client)
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200 and me.json()["username"] == "Mukul_01"


async def test_duplicate_username_is_case_insensitive_and_duplicate_email(client):
    assert (await register(client)).status_code == 201
    r = await register(client, username="mukul_01", email="other@example.com")
    assert r.status_code == 409 and r.json()["error"]["code"] == "username_taken"
    r = await register(client, username="Someone", email="MUKUL@example.com")
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"


async def test_register_validation_errors(client):
    for bad in (
        {"password": "short"},
        {"username": "a b"},
        {"username": "ab"},
        {"email": "not-an-email"},
        {"password": "x" * 129},
    ):
        r = await register(client, **bad)
        assert r.status_code == 422, bad
        assert r.json()["error"]["code"] == "validation_error"


async def test_login_by_email_and_username(client):
    await register(client)
    client.cookies.clear()
    for ident in ("mukul@example.com", "MUKUL_01", "Mukul@Example.com"):
        r = await client.post("/api/v1/auth/login", json={"identifier": ident, "password": VALID_USER["password"]})
        assert r.status_code == 200, ident
        assert (await client.get("/api/v1/users/me")).status_code == 200


async def test_login_failures_are_indistinguishable(client):
    await register(client)
    client.cookies.clear()
    wrong = await client.post("/api/v1/auth/login", json={"identifier": "mukul_01", "password": "nope-nope-nope"})
    unknown = await client.post("/api/v1/auth/login", json={"identifier": "ghost", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "access_token" not in wrong.headers.get("set-cookie", "")


async def test_inactive_user_cannot_login(client):
    await register(client)
    await _db_rows("SELECT 1")  # warm
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE users SET is_active = false"))
    await engine.dispose()
    client.cookies.clear()
    r = await client.post("/api/v1/auth/login", json={"identifier": "mukul_01", "password": VALID_USER["password"]})
    assert r.status_code == 401


async def test_login_rate_limited_per_ip():
    async with make_client(auth_rate_limit_attempts=3) as c:
        codes = []
        for _ in range(5):
            r = await c.post("/api/v1/auth/login", json={"identifier": "x", "password": "y"})
            codes.append(r.status_code)
        assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
        assert r.headers["retry-after"].isdigit()


async def test_login_rate_limited_per_account_across_ips():
    async with make_client(auth_rate_limit_attempts=3, trust_proxy_headers=True) as c:
        codes = []
        for i in range(5):
            r = await c.post(
                "/api/v1/auth/login",
                json={"identifier": "victim", "password": "guess"},
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
            )
            codes.append(r.status_code)
        assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


async def test_logout_requires_csrf_then_revokes_session(client):
    await register(client)
    assert (await client.post("/api/v1/auth/logout")).status_code == 403
    refresh_cookie = client.cookies.get("refresh_token", path="/api/v1/auth")
    r = await client.post("/api/v1/auth/logout", headers=csrf_headers(client))
    assert r.status_code == 204
    assert (await client.get("/api/v1/users/me")).status_code == 401
    # Old refresh token no longer works even if replayed
    client.cookies.set("refresh_token", refresh_cookie, path="/api/v1/auth")
    client.cookies.set("csrf_token", "tok", path="/")
    r = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "tok"})
    assert r.status_code == 401


async def test_refresh_rotates_and_reuse_revokes_family(client):
    await register(client)
    old = client.cookies.get("refresh_token", path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert r.status_code == 200
    new = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert new and new != old

    # Attacker replays the already-rotated token -> rejected AND whole family revoked
    client.cookies.set("refresh_token", old, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert r.status_code == 401
    client.cookies.set("refresh_token", new, path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert r.status_code == 401, "legitimate token must also be dead after reuse detection"


async def test_refresh_requires_csrf_and_cookie(client):
    await register(client)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 403
    client.cookies.delete("refresh_token", path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))).status_code == 401


async def test_expired_refresh_token_rejected(client):
    await register(client)
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE refresh_tokens SET expires_at = now() - interval '1 minute'"))
    await engine.dispose()
    r = await client.post("/api/v1/auth/refresh", headers=csrf_headers(client))
    assert r.status_code == 401


async def test_only_token_hash_is_stored(client):
    await register(client)
    raw = client.cookies.get("refresh_token", path="/api/v1/auth")
    rows = await _db_rows("SELECT token_hash FROM refresh_tokens")
    assert len(rows) == 1 and rows[0][0] != raw and len(rows[0][0]) == 64


async def test_forged_and_expired_access_tokens_rejected(client):
    s = make_settings()
    uid = str(uuid.uuid4())
    forged = jwt.encode({"sub": uid, "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                        "attacker-secret-attacker-secret-1234567", algorithm="HS256")
    client.cookies.set("access_token", forged)
    assert (await client.get("/api/v1/users/me")).status_code == 401
    expired = jwt.encode({"sub": uid, "type": "access", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                         s.jwt_secret, algorithm="HS256")
    client.cookies.set("access_token", expired)
    assert (await client.get("/api/v1/users/me")).status_code == 401


async def test_cross_origin_mutation_blocked(client):
    r = await client.post(
        "/api/v1/auth/register", json=VALID_USER, headers={"Origin": "https://evil.example"}
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "origin_not_allowed"
    assert (await _db_rows("SELECT 1 FROM users")) == []


async def test_error_shape_is_consistent(client):
    r = await client.get("/api/v1/users/me")
    assert set(r.json()) == {"error"} and {"code", "message"} <= set(r.json()["error"])
    r = await client.get("/api/v1/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "http_404"


async def test_concurrent_registration_creates_single_account(client):
    import asyncio
    results = await asyncio.gather(*[register(client) for _ in range(4)])
    codes = sorted(r.status_code for r in results)
    assert codes.count(201) == 1 and all(c in (201, 409) for c in codes)
    assert len(await _db_rows("SELECT 1 FROM users")) == 1


async def test_spoofed_forwarded_for_prefix_cannot_dodge_ip_rate_limit():
    async with make_client(auth_rate_limit_attempts=3, trust_proxy_headers=True) as c:
        codes = []
        for i in range(5):
            # Attacker rotates the (client-controlled) left part; the trusted proxy appended 203.0.113.9.
            r = await c.post(
                "/api/v1/auth/login",
                json={"identifier": f"user{i}", "password": "guess"},
                headers={"X-Forwarded-For": f"198.51.100.{i}, 203.0.113.9"},
            )
            codes.append(r.status_code)
        assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
