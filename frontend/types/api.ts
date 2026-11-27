export interface User {
  id: string;
  username: string;
  email: string;
  avatar_url: string | null;
  created_at: string;
}

export interface AuthResponse {
  user: User;
}

export interface FieldError {
  field: string;
  message: string;
}

export type Permission = "UNKNOWN" | "GRANTED" | "DENIED";
export type JoinPolicy = "CODE" | "INVITE_ONLY";

export interface Range {
  min: number;
  max: number;
  default?: number;
}

export interface GameConfig {
  room_name_length: Range;
  max_players: Range;
  hide_duration_seconds: Range;
  hunt_duration_seconds: Range;
  clue_interval_seconds: Range;
  join_policies: JoinPolicy[];
  invite_token_ttl_hours: number;
}

export interface Team {
  id: string;
  name: string;
  color: string;
  position: number;
}

export interface Member {
  id: string;
  user_id: string;
  username: string;
  avatar_url: string | null;
  team_id: string | null;
  is_ready: boolean;
  is_host: boolean;
  online: boolean;
  safety_acknowledged: boolean;
  location_permission: Permission;
  camera_permission: Permission;
  joined_at: string;
}

export interface Blocker {
  code: string;
  detail: string | null;
}

export interface RoomDetail {
  id: string;
  room_code: string;
  room_name: string;
  status: "WAITING" | "IN_PROGRESS" | "FINISHED" | "CANCELLED";
  host_user_id: string;
  max_players: number;
  member_count: number;
  join_policy: JoinPolicy;
  auto_balance_teams: boolean;
  hide_duration_seconds: number;
  hunt_duration_seconds: number;
  clue_interval_seconds: number;
  shrinking_zone_enabled: boolean;
  created_at: string;
  teams: Team[];
  members: Member[];
  me: string;
  start_blockers: Blocker[];
  teams_unbalanced: boolean;
}

export interface RoomCreated {
  room: RoomDetail;
  invite_token: string;
  invite_expires_at: string;
}

export interface RoomCreateBody {
  room_name: string;
  max_players: number;
  hide_duration_seconds: number;
  hunt_duration_seconds: number;
  clue_interval_seconds: number;
  shrinking_zone_enabled: boolean;
  join_policy: JoinPolicy;
  auto_balance_teams: boolean;
}
