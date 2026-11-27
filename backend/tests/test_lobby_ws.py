"""Lobby WebSocket tests. Uses Starlette's sync TestClient (httpx can't speak WebSocket)."""

import json

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from tests.conftest import ORIGIN, make_settings

PW = "correct-horse-battery"
HEADERS = {"Origin": ORIGIN}


@pytest.fixture
def web():
    app = create_app(make_settings())
    with TestClient(app, headers=HEADERS) as c:
        yield c


def signup(c: TestClient, name: str) -> None:
    c.cookies.clear()
    r = c.post("/api/v1/auth/register", json={"username": name, "email": f"{name.lower()}@example.com", "password": PW})
    assert r.status_code == 201, r.text


def login(c: TestClient, name: str) -> None:
    c.cookies.clear()
    assert c.post("/api/v1/auth/login", json={"identifier": name, "password": PW}).status_code == 200


def api(c: TestClient, method: str, url: str, body=None):
    return c.request(method, url, json=body, headers={**HEADERS, "X-CSRF-Token": c.cookies.get("csrf_token") or ""})


def make_room(c: TestClient) -> dict:
    return api(c, "POST", "/api/v1/rooms", {"room_name": "Socket Room"}).json()["room"]


def ws(c: TestClient, room_id: str, **kw):
    return c.websocket_connect(f"/ws/rooms/{room_id}", headers=kw.get("headers", HEADERS))


def expect_rejected(c: TestClient, room_id: str, **kw):
    with pytest.raises(Exception) as exc:  # pre-accept close surfaces as a denial or disconnect
        with ws(c, room_id, **kw):
            pass
    return exc.value


def test_anonymous_socket_rejected(web):
    signup(web, "Hosty")
    room = make_room(web)
    web.cookies.clear()
    expect_rejected(web, room["id"])


def test_non_member_rejected(web):
    signup(web, "Hosty")
    room = make_room(web)
    signup(web, "Outsider")
    expect_rejected(web, room["id"])


def test_foreign_origin_rejected(web):
    signup(web, "Hosty")
    room = make_room(web)
    expect_rejected(web, room["id"], headers={"Origin": "https://evil.example"})


def test_member_gets_live_updates_and_presence(web):
    signup(web, "Hosty")
    room = make_room(web)
    signup(web, "Pippa")
    code = room["room_code"]
    login(web, "Hosty")
    with ws(web, room["id"]) as host_ws:
        # Host socket opened -> host shows online
        assert api(web, "GET", f"/api/v1/rooms/{room['id']}").json()["members"][0]["online"] is True
        host_ws.receive_text()  # drain own "came online" signal

        login(web, "Pippa")
        assert api(web, "POST", "/api/v1/rooms/join", {"room_code": code}).status_code == 200
        msg = json.loads(host_ws.receive_text())
        assert msg == {"type": "room:updated", "version": 1}  # content-free: no player data on the wire

        host_ws.send_text(json.dumps({"type": "ping"}))
        for _ in range(3):  # a pong arrives, possibly after other content-free signals
            if json.loads(host_ws.receive_text())["type"] == "pong":
                break
        else:
            pytest.fail("no pong received")


def test_leaving_the_room_closes_your_socket(web):
    signup(web, "Hosty")
    room = make_room(web)
    signup(web, "Pippa")
    api(web, "POST", "/api/v1/rooms/join", {"room_code": room["room_code"]})
    with ws(web, room["id"]) as pippa_ws:
        pippa_ws.receive_text()
        assert api(web, "POST", f"/api/v1/rooms/{room['id']}/leave").status_code == 204
        with pytest.raises(WebSocketDisconnect) as exc:
            for _ in range(5):
                pippa_ws.receive_text()
        assert exc.value.code == 4000


def test_oversized_message_closes_socket(web):
    signup(web, "Hosty")
    room = make_room(web)
    with ws(web, room["id"]) as s:
        s.receive_text()
        s.send_text("x" * 2000)
        with pytest.raises(WebSocketDisconnect) as exc:
            for _ in range(5):
                s.receive_text()
        assert exc.value.code == 1008


def test_closing_the_socket_clears_presence(web):
    import time

    signup(web, "Hosty")
    room = make_room(web)
    url = f"/api/v1/rooms/{room['id']}"
    with ws(web, room["id"]) as s:
        s.receive_text()
        assert api(web, "GET", url).json()["members"][0]["online"] is True
    for _ in range(40):  # cleanup runs just after the client disconnects
        if api(web, "GET", url).json()["members"][0]["online"] is False:
            break
        time.sleep(0.1)
    else:
        pytest.fail("presence was not cleared after disconnect")
