import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TeamCard } from "@/components/lobby/TeamCard";
import type { Member, Team } from "@/types/api";

const red: Team = { id: "r", name: "Red", color: "#EF4444", position: 0 };
const blue: Team = { id: "b", name: "Blue", color: "#3B82F6", position: 1 };
const member = (over: Partial<Member>): Member => ({
  id: "m1", user_id: "u1", username: "Pippa", avatar_url: null, team_id: "r", is_ready: true, is_host: false, online: true,
  safety_acknowledged: true, location_permission: "GRANTED", camera_permission: "DENIED", joined_at: "", ...over,
});

describe("TeamCard", () => {
  it("shows status for each player", () => {
    render(<TeamCard team={red} members={[member({})]} allTeams={[red, blue]} meId="other" viewerIsHost={false} onMove={vi.fn()} busy={false} />);
    expect(screen.getByRole("heading", { name: "Team Red" })).toBeInTheDocument();
    expect(screen.getByText("Online")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Location on")).toBeInTheDocument();
    expect(screen.getByText("Camera blocked")).toBeInTheDocument();
  });

  it("offers team moves only to the host, and only to other teams", async () => {
    const onMove = vi.fn();
    const { rerender } = render(<TeamCard team={red} members={[member({})]} allTeams={[red, blue]} meId="x" viewerIsHost={false} onMove={onMove} busy={false} />);
    expect(screen.queryByRole("button", { name: /move pippa/i })).not.toBeInTheDocument();

    rerender(<TeamCard team={red} members={[member({})]} allTeams={[red, blue]} meId="x" viewerIsHost onMove={onMove} busy={false} />);
    expect(screen.queryByRole("button", { name: "Move Pippa to Red" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Move Pippa to Blue" }));
    expect(onMove).toHaveBeenCalledWith("m1", "b");
  });

  it("shows an empty state", () => {
    render(<TeamCard team={blue} members={[]} allTeams={[red, blue]} meId="x" viewerIsHost={false} onMove={vi.fn()} busy={false} />);
    expect(screen.getByText("No players yet.")).toBeInTheDocument();
  });
});
