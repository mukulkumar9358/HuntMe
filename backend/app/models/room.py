import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, Integer, SmallInteger, String, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class GameRoom(Base):
    __tablename__ = "game_rooms"
    __table_args__ = (
        CheckConstraint("max_players BETWEEN 2 AND 10", name="max_players_range"),
        CheckConstraint("status IN ('WAITING','IN_PROGRESS','FINISHED','CANCELLED')", name="status_valid"),
        CheckConstraint("join_policy IN ('CODE','INVITE_ONLY')", name="join_policy_valid"),
        CheckConstraint(
            "hide_duration_seconds > 0 AND hunt_duration_seconds > 0 AND clue_interval_seconds > 0",
            name="durations_positive",
        ),
        Index("uq_game_rooms_invite_token_hash", "invite_token_hash", unique=True,
              postgresql_where=text("invite_token_hash IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_code: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    invite_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    room_name: Mapped[str] = mapped_column(String(40), nullable=False)
    host_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    max_players: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default=text("10"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="WAITING", server_default=text("'WAITING'"))
    join_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="CODE", server_default=text("'CODE'"))
    auto_balance_teams: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=text("true"))
    hide_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120, server_default=text("120"))
    hunt_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=600, server_default=text("600"))
    shrinking_zone_enabled: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("false"))
    clue_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120, server_default=text("120"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("room_id", "name", name="uq_teams_room_id_name"),
        UniqueConstraint("room_id", "position", name="uq_teams_room_id_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RoomMember(Base):
    """A user's membership in a room. Leaving sets ``left_at``; re-joining creates a new row."""

    __tablename__ = "room_members"
    __table_args__ = (
        CheckConstraint("location_permission IN ('UNKNOWN','GRANTED','DENIED')", name="location_permission_valid"),
        CheckConstraint("camera_permission IN ('UNKNOWN','GRANTED','DENIED')", name="camera_permission_valid"),
        Index("uq_room_members_active", "room_id", "user_id", unique=True, postgresql_where=text("left_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("game_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    is_ready: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("false"))
    safety_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Client-reported and informational only: never used for game decisions.
    location_permission: Mapped[str] = mapped_column(String(10), nullable=False, default="UNKNOWN", server_default=text("'UNKNOWN'"))
    camera_permission: Mapped[str] = mapped_column(String(10), nullable=False, default="UNKNOWN", server_default=text("'UNKNOWN'"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
