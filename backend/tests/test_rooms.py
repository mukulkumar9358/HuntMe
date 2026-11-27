import asyncio
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.lobby_rules import ROOM_CODE_ALPHABET
from tests.conftest import csrf_headers, make_client, patch, post, sql

ROOM_BODY = {"room_name": "Evening Hunt"}


async def create(host, **overrides):
    r = await post(host, "/api/v1/rooms", {**ROOM_BODY, **overrides})
    assert r.status_code == 201, r.text
    return r.json()


async def join_code(client, code):
    return await post(client, "/api/v1/rooms/join", {"room_code": code})


async def join_token(client, token):
    return await post(client, "/api/v1/rooms/join", {"invite_token": token})


def team_ids(room):
    return {t["name"]: t["id"] for t in room["teams"]}


def member(room, username):
    return next(m for m in room["members"] if m["username"] == username)


# ----------------------------------------------------------------------------- create
async def test_create_room_defaults_teams_and_host_membership(players):
    host = await players("Host")
    data = await create(host)
    room = data["room"]
    assert room["status"] == "WAITING" and room["member_count"] == 1
    assert len(room["room_code"]) == 8 and set(room["room_code"]) <= set(ROOM_CODE_ALPHABET)
    assert room["hide_duration_seconds"] == 120 and room["hunt_duration_seconds"] == 600  # server defaults
    assert [(t["name"], t["color"], t["position"]) for t in room["teams"]] == [("Red", "#EF4444", 0), ("Blue", "#3B82F6", 1)]
    host_m = member(room, "Host")
    assert host_m["is_host"] and host_m["team_id"] == team_ids(room)["Red"] and room["me"] == host_m["id"]
    assert [b["code"] for b in room["start_blockers"]] == [
        "need_two_players", "team_empty", "host_not_ready", "safety_unacknowledged", "arena_missing",
    ]


async def test_invite_token_is_stored_only_as_hash(players):
    host = await players("Host")
    data = await create(host)
    (row,) = await sql("SELECT invite_token_hash FROM game_rooms")
    assert row[0] != data["invite_token"] and len(row[0]) == 64


async def test_create_requires_auth_and_csrf(players):
    host = await players("Host")
    assert (await host.post("/api/v1/rooms", json=ROOM_BODY)).status_code == 403  # no CSRF header
    async with make_client() as anon:
        assert (await anon.post("/api/v1/rooms", json=ROOM_BODY)).status_code in (401, 403)


@pytest.mark.parametrize("patch_body", [
    {"max_players": 1}, {"max_players": 11}, {"hide_duration_seconds": 5}, {"hunt_duration_seconds": 5000},
    {"clue_interval_seconds": 1}, {"room_name": "ab"}, {"room_name": "x" * 41}, {"join_policy": "OPEN"},
])
async def test_create_validation(players, patch_body):
    host = await players("Host")
    r = await post(host, "/api/v1/rooms", {**ROOM_BODY, **patch_body})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert await sql("SELECT 1 FROM game_rooms") == []


async def test_game_config_exposes_server_limits(players):
    host = await players("Host")
    cfg = (await host.get("/api/v1/game-config")).json()
    assert cfg["max_players"] == {"min": 2, "max": 10, "default": 10}
    assert cfg["hide_duration_seconds"]["default"] == 120 and cfg["hunt_duration_seconds"]["default"] == 600


# ------------------------------------------------------------------------------- join
async def test_join_by_code_normalises_input_and_auto_balances(players):
    host = await players("Host")
    room = (await create(host))["room"]
    messy = f" {room['room_code'][:4].lower()}-{room['room_code'][4:].lower()} "
    names = ["Pip", "Pax", "Pam"]
    detail = None
    for n in names:
        c = await players(n)
        r = await join_code(c, messy)
        assert r.status_code == 200, r.text
        detail = r.json()
    sizes = {t["name"]: sum(1 for m in detail["members"] if m["team_id"] == t["id"]) for t in detail["teams"]}
    assert sizes == {"Red": 2, "Blue": 2}
    assert detail["teams_unbalanced"] is False


async def test_duplicate_join_is_idempotent(players):
    host, p = await players("Host"), await players("Pip")
    code = (await create(host))["room"]["room_code"]
    assert (await join_code(p, code)).status_code == 200
    r = await join_code(p, code)
    assert r.status_code == 200 and r.json()["member_count"] == 2
    assert len(await sql("SELECT 1 FROM room_members WHERE left_at IS NULL")) == 2


async def test_unknown_expired_and_blocked_joins_all_look_identical(players):
    host, p = await players("Host"), await players("Pip")
    invite_only = await create(host, join_policy="INVITE_ONLY")
    failures = [
        await join_code(p, "ZZZZZZZZ"),
        await join_code(p, invite_only["room"]["room_code"]),  # code alone isn't enough for invite-only
        await join_token(p, "not-a-real-token"),
    ]
    assert all(f.status_code == 404 for f in failures)
    assert len({f.text for f in failures}) == 1 and failures[0].json()["error"]["code"] == "room_not_found"


async def test_join_requires_exactly_one_of_code_or_token(players):
    p = await players("Pip")
    assert (await post(p, "/api/v1/rooms/join", {})).status_code == 422
    assert (await post(p, "/api/v1/rooms/join", {"room_code": "ABCDEFGH", "invite_token": "x"})).status_code == 422


async def test_room_full(players):
    host, p1, p2 = await players("Host"), await players("Pip"), await players("Pax")
    code = (await create(host, max_players=2))["room"]["room_code"]
    assert (await join_code(p1, code)).status_code == 200
    r = await join_code(p2, code)
    assert r.status_code == 409 and r.json()["error"]["code"] == "room_full"


async def test_concurrent_joins_never_exceed_capacity(players):
    host = await players("Host")
    code = (await create(host, max_players=3))["room"]["room_code"]
    joiners = [await players(f"Pl{i}") for i in range(6)]
    results = await asyncio.gather(*[join_code(c, code) for c in joiners])
    codes = sorted(r.status_code for r in results)
    assert codes.count(200) == 2 and codes.count(409) == 4, codes
    assert len(await sql("SELECT 1 FROM room_members WHERE left_at IS NULL")) == 3


async def test_cannot_join_a_started_or_cancelled_room(players):
    host, p, q = await players("Host"), await players("Pip"), await players("Pax")
    code = (await create(host))["room"]["room_code"]
    await sql("UPDATE game_rooms SET status = 'IN_PROGRESS'")
    r = await join_code(p, code)
    assert r.status_code == 409 and r.json()["error"]["code"] == "room_in_progress"
    await sql("UPDATE game_rooms SET status = 'CANCELLED'")
    assert (await join_code(q, code)).status_code == 404


async def test_manual_team_mode_leaves_joiners_unassigned(players):
    host, p = await players("Host"), await players("Pip")
    code = (await create(host, auto_balance_teams=False))["room"]["room_code"]
    detail = (await join_code(p, code)).json()
    assert member(detail, "Pip")["team_id"] is None
    assert ("unassigned_members", "1") in [(b["code"], b["detail"]) for b in detail["start_blockers"]]


# -------------------------------------------------------------------- invite links
async def test_invite_only_rooms_join_by_token_and_tokens_can_be_revoked(players):
    host, a, b, stranger = await players("Host"), await players("Ann"), await players("Bob"), await players("Stranger")
    data = await create(host, join_policy="INVITE_ONLY")
    first = data["invite_token"]
    assert (await join_token(a, first)).status_code == 200

    new = (await post(host, f"/api/v1/rooms/{data['room']['id']}/invite")).json()["invite_token"]
    assert new != first
    assert (await join_token(b, first)).status_code == 404  # old link revoked
    assert (await join_token(b, new)).status_code == 200

    assert (await post(a, f"/api/v1/rooms/{data['room']['id']}/invite")).status_code == 403  # member, not host
    assert (await post(stranger, f"/api/v1/rooms/{data['room']['id']}/invite")).status_code == 404  # not a member


async def test_expired_invite_token_is_rejected(players):
    host, p = await players("Host"), await players("Pip")
    token = (await create(host))["invite_token"]
    await sql("UPDATE game_rooms SET invite_expires_at = now() - interval '1 minute'")
    assert (await join_token(p, token)).status_code == 404


# ------------------------------------------------------------------------- visibility
async def test_only_members_can_read_a_room(players):
    host, stranger = await players("Host"), await players("Stranger")
    room_id = (await create(host))["room"]["id"]
    assert (await host.get(f"/api/v1/rooms/{room_id}")).status_code == 200
    assert (await stranger.get(f"/api/v1/rooms/{room_id}")).status_code == 404
    assert (await stranger.get(f"/api/v1/rooms/{room_id}/members")).status_code == 404
    assert (await host.get(f"/api/v1/rooms/{uuid.uuid4()}")).status_code == 404
    async with make_client() as anon:
        assert (await anon.get(f"/api/v1/rooms/{room_id}")).status_code == 401


async def test_members_endpoint(players):
    host, p = await players("Host"), await players("Pip")
    room = (await create(host))["room"]
    await join_code(p, room["room_code"])
    members = (await host.get(f"/api/v1/rooms/{room['id']}/members")).json()
    assert [m["username"] for m in members] == ["Host", "Pip"]


# ----------------------------------------------------------------------------- teams
async def test_host_can_move_players_between_teams(players):
    host, p = await players("Host"), await players("Pip")
    room = (await create(host))["room"]
    detail = (await join_code(p, room["room_code"])).json()
    blue = team_ids(detail)["Blue"]
    pid = member(detail, "Pip")["id"]
    r = await patch(host, f"/api/v1/rooms/{room['id']}/members/{pid}/team", {"team_id": team_ids(detail)["Red"]})
    assert r.status_code == 200 and member(r.json(), "Pip")["team_id"] == team_ids(detail)["Red"]
    assert r.json()["teams_unbalanced"] is True  # 2 vs 0
    r = await patch(host, f"/api/v1/rooms/{room['id']}/members/{pid}/team", {"team_id": blue})
    assert member(r.json(), "Pip")["team_id"] == blue
    assert r.json()["teams_unbalanced"] is False  # 1 vs 1
    # Both views agree
    assert member((await p.get(f"/api/v1/rooms/{room['id']}")).json(), "Pip")["team_id"] == blue


async def test_team_changes_are_host_only_and_validated(players):
    host, p, outsider = await players("Host"), await players("Pip"), await players("Out")
    room = (await create(host))["room"]
    detail = (await join_code(p, room["room_code"])).json()
    host_id, p_id = member(detail, "Host")["id"], member(detail, "Pip")["id"]
    red = team_ids(detail)["Red"]
    url = lambda mid: f"/api/v1/rooms/{room['id']}/members/{mid}/team"  # noqa: E731

    assert (await patch(p, url(host_id), {"team_id": red})).status_code == 403          # non-host member
    assert (await patch(p, url(p_id), {"team_id": red})).status_code == 403             # not even for yourself
    assert (await patch(outsider, url(p_id), {"team_id": red})).status_code == 404      # not in the room
    assert (await patch(host, url(uuid.uuid4()), {"team_id": red})).status_code == 404  # unknown member

    other_room = (await create(outsider, room_name="Other Room"))["room"]
    foreign_team = other_room["teams"][0]["id"]
    r = await patch(host, url(p_id), {"team_id": foreign_team})
    assert r.status_code == 404 and r.json()["error"]["code"] == "team_not_found"       # team from another room

    await sql("UPDATE game_rooms SET status = 'IN_PROGRESS' WHERE room_code = '%s'" % room["room_code"])
    r = await patch(host, url(p_id), {"team_id": red})
    assert r.status_code == 409 and r.json()["error"]["code"] == "room_not_editable"


# ------------------------------------------------------------------------ ready state
async def test_ready_requires_team_and_safety_ack(players):
    host, p = await players("Host"), await players("Pip")
    room = (await create(host, auto_balance_teams=False))["room"]
    await join_code(p, room["room_code"])
    url = f"/api/v1/rooms/{room['id']}/members/me"

    r = await patch(p, url, {"is_ready": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_on_team"

    r = await patch(host, url, {"is_ready": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "safety_not_acknowledged"

    r = await patch(host, url, {"safety_acknowledged": True, "is_ready": True})  # both in one request
    assert r.status_code == 200 and member(r.json(), "Host")["is_ready"] is True

    r = await patch(host, url, {"safety_acknowledged": False})  # withdrawing consent un-readies you
    m = member(r.json(), "Host")
    assert m["safety_acknowledged"] is False and m["is_ready"] is False


async def test_permission_indicators_are_stored_but_validated(players):
    host = await players("Host")
    room = (await create(host))["room"]
    url = f"/api/v1/rooms/{room['id']}/members/me"
    r = await patch(host, url, {"location_permission": "GRANTED", "camera_permission": "DENIED"})
    m = member(r.json(), "Host")
    assert (m["location_permission"], m["camera_permission"]) == ("GRANTED", "DENIED")
    assert (await patch(host, url, {"location_permission": "MAYBE"})).status_code == 422


async def test_lobby_is_startable_except_for_missing_arena(players):
    host, p = await players("Host"), await players("Pip")
    room = (await create(host))["room"]
    await join_code(p, room["room_code"])
    url = f"/api/v1/rooms/{room['id']}/members/me"
    await patch(p, url, {"safety_acknowledged": True})
    detail = (await patch(host, url, {"safety_acknowledged": True, "is_ready": True})).json()
    assert [b["code"] for b in detail["start_blockers"]] == ["arena_missing"]  # Stage 3 removes this


# --------------------------------------------------------------------------- leaving
async def test_member_can_leave_and_rejoin(players):
    host, p = await players("Host"), await players("Pip")
    room = (await create(host))["room"]
    await join_code(p, room["room_code"])
    assert (await post(p, f"/api/v1/rooms/{room['id']}/leave")).status_code == 204
    assert (await p.get(f"/api/v1/rooms/{room['id']}")).status_code == 404
    assert (await host.get(f"/api/v1/rooms/{room['id']}")).json()["member_count"] == 1
    assert (await post(p, f"/api/v1/rooms/{room['id']}/leave")).status_code == 404  # already gone

    r = await join_code(p, room["room_code"])
    assert r.status_code == 200 and r.json()["member_count"] == 2
    assert len(await sql("SELECT 1 FROM room_members WHERE left_at IS NULL")) == 2
    assert len(await sql("SELECT 1 FROM room_members")) == 3  # history kept; only one active row per user


async def test_host_leaving_hands_over_to_longest_standing_member(players):
    host, a, b = await players("Host"), await players("Ann"), await players("Bob")
    room = (await create(host))["room"]
    await join_code(a, room["room_code"])
    await join_code(b, room["room_code"])
    assert (await post(host, f"/api/v1/rooms/{room['id']}/leave")).status_code == 204
    detail = (await b.get(f"/api/v1/rooms/{room['id']}")).json()
    assert member(detail, "Ann")["is_host"] and not member(detail, "Bob")["is_host"]
    # and the new host can now manage teams
    r = await patch(a, f"/api/v1/rooms/{room['id']}/members/{member(detail, 'Bob')['id']}/team", {"team_id": team_ids(detail)["Red"]})
    assert r.status_code == 200


async def test_last_member_leaving_cancels_the_room(players):
    host, p = await players("Host"), await players("Pip")
    data = await create(host)
    await post(host, f"/api/v1/rooms/{data['room']['id']}/leave")
    (row,) = await sql("SELECT status, invite_token_hash FROM game_rooms")
    assert row[0] == "CANCELLED" and row[1] is None
    assert (await join_code(p, data["room"]["room_code"])).status_code == 404


# --------------------------------------------------------------- abuse and integrity
async def test_join_attempts_are_rate_limited(players):
    host = await players("Host")
    guesser = await players("Guesser", room_join_rate_limit_attempts=3)
    codes = [(await join_code(guesser, "ZZZZZZZZ")).status_code for _ in range(5)]
    assert codes == [404, 404, 404, 429, 429]
    assert (await join_code(host, "ZZZZZZZZ")).status_code in (404, 429)  # sanity: still answers


async def test_cross_origin_room_mutation_blocked(players):
    host = await players("Host")
    r = await host.post("/api/v1/rooms", json=ROOM_BODY, headers={**csrf_headers(host), "Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "origin_not_allowed"


async def test_database_forbids_duplicate_active_membership(players):
    host = await players("Host")
    room_id = (await create(host))["room"]["id"]
    with pytest.raises(IntegrityError):
        await sql(f"INSERT INTO room_members (room_id, user_id) SELECT room_id, user_id FROM room_members WHERE room_id = '{room_id}'")
