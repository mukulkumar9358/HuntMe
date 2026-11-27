"""rooms, teams, room_members

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_rooms",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("room_code", sa.String(12), nullable=False),
        sa.Column("invite_token_hash", sa.String(64), nullable=True),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("room_name", sa.String(40), nullable=False),
        sa.Column("host_user_id", sa.Uuid(), nullable=False),
        sa.Column("max_players", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'WAITING'")),
        sa.Column("join_policy", sa.String(16), nullable=False, server_default=sa.text("'CODE'")),
        sa.Column("auto_balance_teams", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("hide_duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("120")),
        sa.Column("hunt_duration_seconds", sa.Integer(), nullable=False, server_default=sa.text("600")),
        sa.Column("shrinking_zone_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("clue_interval_seconds", sa.Integer(), nullable=False, server_default=sa.text("120")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_game_rooms"),
        sa.UniqueConstraint("room_code", name="uq_game_rooms_room_code"),
        sa.ForeignKeyConstraint(["host_user_id"], ["users.id"], name="fk_game_rooms_host_user_id_users", ondelete="RESTRICT"),
        sa.CheckConstraint("max_players BETWEEN 2 AND 10", name="ck_game_rooms_max_players_range"),
        sa.CheckConstraint("status IN ('WAITING','IN_PROGRESS','FINISHED','CANCELLED')", name="ck_game_rooms_status_valid"),
        sa.CheckConstraint("join_policy IN ('CODE','INVITE_ONLY')", name="ck_game_rooms_join_policy_valid"),
        sa.CheckConstraint(
            "hide_duration_seconds > 0 AND hunt_duration_seconds > 0 AND clue_interval_seconds > 0",
            name="ck_game_rooms_durations_positive",
        ),
    )
    op.create_index("ix_game_rooms_host_user_id", "game_rooms", ["host_user_id"])
    op.create_index(
        "uq_game_rooms_invite_token_hash", "game_rooms", ["invite_token_hash"], unique=True,
        postgresql_where=sa.text("invite_token_hash IS NOT NULL"),
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_teams"),
        sa.ForeignKeyConstraint(["room_id"], ["game_rooms.id"], name="fk_teams_room_id_game_rooms", ondelete="CASCADE"),
        sa.UniqueConstraint("room_id", "name", name="uq_teams_room_id_name"),
        sa.UniqueConstraint("room_id", "position", name="uq_teams_room_id_position"),
    )
    op.create_index("ix_teams_room_id", "teams", ["room_id"])

    op.create_table(
        "room_members",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("is_ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("safety_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location_permission", sa.String(10), nullable=False, server_default=sa.text("'UNKNOWN'")),
        sa.Column("camera_permission", sa.String(10), nullable=False, server_default=sa.text("'UNKNOWN'")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_room_members"),
        sa.ForeignKeyConstraint(["room_id"], ["game_rooms.id"], name="fk_room_members_room_id_game_rooms", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_room_members_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_room_members_team_id_teams", ondelete="SET NULL"),
        sa.CheckConstraint("location_permission IN ('UNKNOWN','GRANTED','DENIED')", name="ck_room_members_location_permission_valid"),
        sa.CheckConstraint("camera_permission IN ('UNKNOWN','GRANTED','DENIED')", name="ck_room_members_camera_permission_valid"),
    )
    op.create_index("ix_room_members_room_id", "room_members", ["room_id"])
    op.create_index("ix_room_members_user_id", "room_members", ["user_id"])
    op.create_index(
        "uq_room_members_active", "room_members", ["room_id", "user_id"], unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("room_members")
    op.drop_table("teams")
    op.drop_table("game_rooms")
