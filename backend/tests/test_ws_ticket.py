"""WebSocket ticket auth (production path) and database URL normalisation."""

import json

import pytest
from starlette.testclient import TestClient

from app.core.config import normalize_database_url
from app.infrastructure.ws_ticket import SUBPROTOCOL
from app.main import create_app
from tests.conftest import make_settings
from tests.test_lobby_ws import HEADERS, api, login, make_room, signup


@pytest.fixture
def web():
    app = create_app(make_settings())
    with TestClient(app, headers=HEADERS) as c:
        yield c


def mint(c: TestClient, room_id: str) -> str:
    r = api(c, "POST", f"/api/v1/rooms/{room_id}/ws-ticket")
    assert r.status_code == 200, r.text
    return r.json()["ticket"]


def connect(c: TestClient, room_id: str, ticket: str, headers=HEADERS):
    # No auth cookies are sent: the ticket alone must be enough (this is the cross-host production path).
    c.cookies.clear()
    return c.websocket_connect(f"/ws/rooms/{room_id}", headers=headers, subprotocols=[SUBPROTOCOL, ticket])


def test_ticket_requires_login_and_membership(web):
    signup(web, "Hosty")
    room = make_room(web)
    web.cookies.clear()
    assert api(web, "POST", f"/api/v1/rooms/{room['id']}/ws-ticket").status_code in (401, 403)
    signup(web, "Outsider")
    assert api(web, "POST", f"/api/v1/rooms/{room['id']}/ws-ticket").status_code == 404


def test_ticket_requires_csrf(web):
    signup(web, "Hosty")
    room = make_room(web)
    r = web.post(f"/api/v1/rooms/{room['id']}/ws-ticket", headers=HEADERS)  # no X-CSRF-Token
    assert r.status_code == 403


def test_ticket_connects_without_cookies_and_is_single_use(web):
    signup(web, "Hosty")
    room = make_room(web)
    ticket = mint(web, room["id"])
    with connect(web, room["id"], ticket) as s:
        assert s.accepted_subprotocol == SUBPROTOCOL
        assert json.loads(s.receive_text())["type"] == "room:updated"
    with pytest.raises(Exception):  # replaying the same ticket is rejected
        with connect(web, room["id"], ticket):
            pass


def test_garbage_ticket_rejected(web):
    signup(web, "Hosty")
    room = make_room(web)
    with pytest.raises(Exception):
        with connect(web, room["id"], "not-a-real-ticket"):
            pass


def test_ticket_is_bound_to_its_room(web):
    signup(web, "Hosty")
    room_a = make_room(web)
    room_b = make_room(web)
    ticket = mint(web, room_a["id"])
    with pytest.raises(Exception):
        with connect(web, room_b["id"], ticket):
            pass


def test_ticket_with_foreign_origin_rejected(web):
    signup(web, "Hosty")
    room = make_room(web)
    ticket = mint(web, room["id"])
    with pytest.raises(Exception):
        with connect(web, room["id"], ticket, headers={"Origin": "https://evil.example"}):
            pass


def test_ticket_stops_working_after_leaving_room(web):
    signup(web, "Hosty")
    room = make_room(web)
    signup(web, "Pippa")
    api(web, "POST", "/api/v1/rooms/join", {"room_code": room["room_code"]})
    ticket = mint(web, room["id"])
    assert api(web, "POST", f"/api/v1/rooms/{room['id']}/leave").status_code == 204
    with pytest.raises(Exception):  # membership is re-checked at handshake, not just at mint time
        with connect(web, room["id"], ticket):
            pass
    login(web, "Hosty")  # keep the fixture's cookie jar usable for teardown


def test_normalize_database_url_for_neon():
    url = "postgresql://user:pw@ep-x-pooler.ap-southeast-1.aws.neon.tech/db?sslmode=require&channel_binding=require"
    assert normalize_database_url(url) == (
        "postgresql+asyncpg://user:pw@ep-x-pooler.ap-southeast-1.aws.neon.tech/db?ssl=require"
    )
    assert normalize_database_url("postgres://u:p@h/db").startswith("postgresql+asyncpg://")
    local = "postgresql+asyncpg://huntme:pw@huntme-db:5432/huntme"
    assert normalize_database_url(local) == local
