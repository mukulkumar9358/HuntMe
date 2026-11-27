import { blockerMessage, formatDuration, groupByTeam, inviteUrl, readyBlockReason } from "@/lib/lobby";
import type { Member, RoomDetail } from "@/types/api";

const member = (over: Partial<Member>): Member => ({
  id: "m", user_id: "u", username: "x", avatar_url: null, team_id: null, is_ready: false, is_host: false,
  online: true, safety_acknowledged: false, location_permission: "UNKNOWN", camera_permission: "UNKNOWN", joined_at: "", ...over,
});

describe("blockerMessage", () => {
  it.each([
    [{ code: "need_two_players", detail: null }, /two players/i],
    [{ code: "team_empty", detail: "Blue" }, "Team Blue needs at least one player."],
    [{ code: "unassigned_members", detail: "1" }, "1 player still needs a team."],
    [{ code: "unassigned_members", detail: "3" }, "3 players still need a team."],
    [{ code: "safety_unacknowledged", detail: "2" }, "2 players haven't accepted the safety rules."],
    [{ code: "host_not_ready", detail: null }, /mark yourself ready/i],
    [{ code: "arena_missing", detail: null }, /playing area/i],
    [{ code: "something_new", detail: null }, /isn't ready/i],
  ])("%j", (blocker, expected) => {
    const text = blockerMessage(blocker);
    if (typeof expected === "string") expect(text).toBe(expected);
    else expect(text).toMatch(expected);
  });
});

describe("groupByTeam", () => {
  it("orders teams by position and separates unassigned players", () => {
    const room = {
      teams: [
        { id: "b", name: "Blue", color: "#3B82F6", position: 1 },
        { id: "r", name: "Red", color: "#EF4444", position: 0 },
      ],
      members: [member({ id: "1", team_id: "b" }), member({ id: "2", team_id: "r" }), member({ id: "3", team_id: null })],
    } as Pick<RoomDetail, "teams" | "members">;
    const { groups, unassigned } = groupByTeam(room);
    expect(groups.map((g) => g.team.name)).toEqual(["Red", "Blue"]);
    expect(groups[0].members.map((m) => m.id)).toEqual(["2"]);
    expect(unassigned.map((m) => m.id)).toEqual(["3"]);
  });
});

describe("helpers", () => {
  it("formats durations", () => {
    expect(formatDuration(45)).toBe("45 sec");
    expect(formatDuration(120)).toBe("2 min");
    expect(formatDuration(150)).toBe("2.5 min");
  });
  it("builds an encoded invite url", () => expect(inviteUrl("https://x.test", "a/b+c")).toBe("https://x.test/join-room?invite=a%2Fb%2Bc"));
  it("explains why ready is unavailable, mirroring the server", () => {
    expect(readyBlockReason(member({ team_id: null }))).toMatch(/team/i);
    expect(readyBlockReason(member({ team_id: "r", safety_acknowledged: false }))).toMatch(/safety/i);
    expect(readyBlockReason(member({ team_id: "r", safety_acknowledged: true }))).toBeNull();
  });
});
