import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RegisterForm } from "@/components/auth/RegisterForm";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }), useSearchParams: () => new URLSearchParams("next=/create-room") }));

function setup() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RegisterForm />
    </QueryClientProvider>,
  );
}

async function fill(user: ReturnType<typeof userEvent.setup>, v: { u: string; e: string; p: string; c: string }) {
  await user.type(screen.getByLabelText("Username"), v.u);
  await user.type(screen.getByLabelText("Email"), v.e);
  await user.type(screen.getByLabelText("Password"), v.p);
  await user.type(screen.getByLabelText("Confirm password"), v.c);
  await user.click(screen.getByRole("button", { name: /create account/i }));
}

afterEach(() => {
  vi.restoreAllMocks();
  push.mockReset();
});

describe("RegisterForm", () => {
  it("shows validation errors without calling the API", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    setup();
    await fill(userEvent.setup(), { u: "ab", e: "bad", p: "short", c: "other" });
    expect(await screen.findByText("Use 3–24 letters, numbers or underscores.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Passwords don't match.")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("maps a server 'username_taken' error onto the username field", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "username_taken", message: "That username is already taken." } }), { status: 409 }),
    );
    setup();
    await fill(userEvent.setup(), { u: "taken_name", e: "a@b.com", p: "long-enough-pass", c: "long-enough-pass" });
    expect(await screen.findByText("That username is already taken.")).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toHaveAttribute("aria-invalid", "true");
    expect(push).not.toHaveBeenCalled();
  });

  it("redirects to ?next after success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ user: { id: "1", username: "ok_name", email: "a@b.com", avatar_url: null, created_at: "" } }), { status: 201 }),
    );
    setup();
    await fill(userEvent.setup(), { u: "ok_name", e: "a@b.com", p: "long-enough-pass", c: "long-enough-pass" });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/create-room"));
  });
});
