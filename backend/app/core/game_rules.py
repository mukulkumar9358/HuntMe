"""Server-enforced limits for room settings. The frontend reads these from GET /api/v1/game-config."""

from dataclasses import dataclass

from app.core.config import Settings

ROOM_NAME_MIN, ROOM_NAME_MAX = 3, 40
PLAYERS_MIN, PLAYERS_MAX = 2, 10
HIDE_MIN, HIDE_MAX = 30, 600
HUNT_MIN, HUNT_MAX = 120, 3600
CLUE_MIN, CLUE_MAX = 30, 900

ROOM_STATUSES = ("WAITING", "IN_PROGRESS", "FINISHED", "CANCELLED")
JOIN_POLICIES = ("CODE", "INVITE_ONLY")
PERMISSION_STATES = ("UNKNOWN", "GRANTED", "DENIED")

TEAM_DEFS = (("Red", "#EF4444"), ("Blue", "#3B82F6"))  # position 0 = Red, 1 = Blue (MVP: fixed names/colours)


@dataclass(frozen=True)
class Range:
    min: int
    max: int
    default: int | None = None


def game_config(settings: Settings) -> dict:
    return {
        "room_name_length": Range(ROOM_NAME_MIN, ROOM_NAME_MAX).__dict__,
        "max_players": Range(PLAYERS_MIN, PLAYERS_MAX, PLAYERS_MAX).__dict__,
        "hide_duration_seconds": Range(HIDE_MIN, HIDE_MAX, settings.default_hide_duration_seconds).__dict__,
        "hunt_duration_seconds": Range(HUNT_MIN, HUNT_MAX, settings.default_hunt_duration_seconds).__dict__,
        "clue_interval_seconds": Range(CLUE_MIN, CLUE_MAX, 120).__dict__,
        "join_policies": list(JOIN_POLICIES),
        "invite_token_ttl_hours": settings.invite_token_ttl_hours,
    }
