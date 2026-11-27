import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core import game_rules as rules

Permission = Literal["UNKNOWN", "GRANTED", "DENIED"]


class RoomCreate(BaseModel):
    room_name: str
    max_players: int = Field(default=rules.PLAYERS_MAX, ge=rules.PLAYERS_MIN, le=rules.PLAYERS_MAX)
    # None means "use the server default" (the frontend never hardcodes these).
    hide_duration_seconds: int | None = Field(default=None, ge=rules.HIDE_MIN, le=rules.HIDE_MAX)
    hunt_duration_seconds: int | None = Field(default=None, ge=rules.HUNT_MIN, le=rules.HUNT_MAX)
    clue_interval_seconds: int | None = Field(default=None, ge=rules.CLUE_MIN, le=rules.CLUE_MAX)
    shrinking_zone_enabled: bool = False
    join_policy: Literal["CODE", "INVITE_ONLY"] = "CODE"
    auto_balance_teams: bool = True

    @field_validator("room_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not rules.ROOM_NAME_MIN <= len(v) <= rules.ROOM_NAME_MAX:
            raise ValueError(f"Use {rules.ROOM_NAME_MIN}–{rules.ROOM_NAME_MAX} characters.")
        return v


class JoinRequest(BaseModel):
    room_code: str | None = Field(default=None, min_length=1, max_length=32)
    invite_token: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def _exactly_one(self) -> "JoinRequest":
        if bool(self.room_code) == bool(self.invite_token):
            raise ValueError("Provide either a room code or an invite token.")
        return self


class MemberUpdate(BaseModel):
    is_ready: bool | None = None
    safety_acknowledged: bool | None = None
    location_permission: Permission | None = None
    camera_permission: Permission | None = None


class TeamAssign(BaseModel):
    team_id: uuid.UUID


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    position: int


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    avatar_url: str | None
    team_id: uuid.UUID | None
    is_ready: bool
    is_host: bool
    online: bool
    safety_acknowledged: bool
    location_permission: Permission
    camera_permission: Permission
    joined_at: datetime


class BlockerOut(BaseModel):
    code: str
    detail: str | None = None


class RoomDetail(BaseModel):
    id: uuid.UUID
    room_code: str
    room_name: str
    status: str
    host_user_id: uuid.UUID
    max_players: int
    member_count: int
    join_policy: str
    auto_balance_teams: bool
    hide_duration_seconds: int
    hunt_duration_seconds: int
    clue_interval_seconds: int
    shrinking_zone_enabled: bool
    created_at: datetime
    teams: list[TeamOut]
    members: list[MemberOut]
    me: uuid.UUID  # the viewer's member id
    start_blockers: list[BlockerOut]
    teams_unbalanced: bool


class RoomCreated(BaseModel):
    room: RoomDetail
    invite_token: str
    invite_expires_at: datetime


class InviteOut(BaseModel):
    invite_token: str
    invite_expires_at: datetime
