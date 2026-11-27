import uuid

from app.services.lobby_rules import (
    ROOM_CODE_ALPHABET, MemberView, TeamView, generate_room_code, normalize_room_code, pick_team,
    start_blockers, teams_unbalanced,
)

RED, BLUE = TeamView(uuid.uuid4(), "Red"), TeamView(uuid.uuid4(), "Blue")
HOST, P2 = uuid.uuid4(), uuid.uuid4()


def codes(blockers):
    return [b.code for b in blockers]


def test_room_codes_use_unambiguous_alphabet_and_are_unique():
    seen = {generate_room_code() for _ in range(2000)}
    assert len(seen) == 2000
    assert all(len(c) == 8 and set(c) <= set(ROOM_CODE_ALPHABET) for c in seen)
    assert not set("01ILO") & set(ROOM_CODE_ALPHABET)


def test_normalize_room_code():
    assert normalize_room_code(" abcd-efgh ") == "ABCDEFGH"
    assert normalize_room_code("ab cd\tef-gh") == "ABCDEFGH"


def test_pick_team_prefers_smaller_then_first():
    a, b = uuid.uuid4(), uuid.uuid4()
    assert pick_team([(a, 0), (b, 0)]) == a
    assert pick_team([(a, 2), (b, 1)]) == b
    assert pick_team([(a, 1), (b, 1)]) == a


def test_teams_unbalanced_only_when_gap_exceeds_one():
    assert not teams_unbalanced([2, 3]) and not teams_unbalanced([1, 1])
    assert teams_unbalanced([1, 3]) and not teams_unbalanced([])


def test_start_blockers_empty_lobby_with_one_host():
    m = [MemberView(HOST, RED.id, False, False)]
    assert codes(start_blockers(members=m, teams=[RED, BLUE], host_user_id=HOST, has_arena=False)) == [
        "need_two_players", "team_empty", "host_not_ready", "safety_unacknowledged", "arena_missing",
    ]


def test_start_blockers_clear_when_everything_is_in_place():
    m = [MemberView(HOST, RED.id, True, True), MemberView(P2, BLUE.id, False, True)]  # P2 un-ready is fine
    assert start_blockers(members=m, teams=[RED, BLUE], host_user_id=HOST, has_arena=True) == []


def test_unassigned_members_block_and_report_count():
    m = [MemberView(HOST, RED.id, True, True), MemberView(P2, None, False, True)]
    b = start_blockers(members=m, teams=[RED, BLUE], host_user_id=HOST, has_arena=True)
    assert ("unassigned_members", "1") in [(x.code, x.detail) for x in b]
    assert ("team_empty", "Blue") in [(x.code, x.detail) for x in b]
