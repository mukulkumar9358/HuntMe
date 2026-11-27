"""Pure lobby rules: room codes, team balancing, and what blocks a match from starting.

No database or network access here, so every rule is unit-testable.
"""

import re
import secrets
import uuid
from dataclasses import dataclass

# 31 symbols: no 0/O, 1/I/L. Eight characters give ~8.5e11 codes; joins are rate limited on top of that.
ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 8
_CODE_STRIP = re.compile(r"[\s\-]")


def generate_room_code(length: int = ROOM_CODE_LENGTH) -> str:
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(length))


def normalize_room_code(raw: str) -> str:
    return _CODE_STRIP.sub("", raw).upper()


def pick_team(team_sizes: list[tuple[uuid.UUID, int]]) -> uuid.UUID:
    """Smallest team wins; ties go to the earliest team (input is ordered by position)."""
    return min(enumerate(team_sizes), key=lambda it: (it[1][1], it[0]))[1][0]


@dataclass(frozen=True)
class MemberView:
    user_id: uuid.UUID
    team_id: uuid.UUID | None
    is_ready: bool
    safety_acknowledged: bool


@dataclass(frozen=True)
class TeamView:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class Blocker:
    code: str
    detail: str | None = None


def start_blockers(
    *, members: list[MemberView], teams: list[TeamView], host_user_id: uuid.UUID, has_arena: bool
) -> list[Blocker]:
    """Reasons the host cannot start yet. Empty list means the lobby is ready.

    Not blockers on purpose: other players being un-ready (the host decides when to go), and uneven teams
    (a hint, not a rule).
    """
    blockers: list[Blocker] = []
    assigned = [m for m in members if m.team_id is not None]
    if len(assigned) < 2:
        blockers.append(Blocker("need_two_players"))
    for t in teams:
        if not any(m.team_id == t.id for m in members):
            blockers.append(Blocker("team_empty", t.name))
    unassigned = len(members) - len(assigned)
    if unassigned:
        blockers.append(Blocker("unassigned_members", str(unassigned)))
    host = next((m for m in members if m.user_id == host_user_id), None)
    if host is None or not host.is_ready:
        blockers.append(Blocker("host_not_ready"))
    unacked = sum(1 for m in members if not m.safety_acknowledged)
    if unacked:
        blockers.append(Blocker("safety_unacknowledged", str(unacked)))
    if not has_arena:
        blockers.append(Blocker("arena_missing"))
    return blockers


def teams_unbalanced(sizes: list[int]) -> bool:
    return bool(sizes) and max(sizes) - min(sizes) > 1
