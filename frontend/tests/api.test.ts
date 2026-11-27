import { ApiError, api } from "@/services/api";

function json(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "csrf_token=; max-age=0";
});

describe("api()", () => {
  it("maps the backend error shape to ApiError", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json(409, { error: { code: "email_taken", message: "Taken.", details: [{ field: "email", message: "x" }] } }));
    await expect(api("/auth/register", { method: "POST", body: {} })).rejects.toMatchObject({ status: 409, code: "email_taken", message: "Taken." });
  });

  it("sends the CSRF header on unsafe methods only", async () => {
    document.cookie = "csrf_token=abc123";
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(json(204));
    await api("/auth/logout", { method: "POST" });
    await api("/users/me");
    expect((spy.mock.calls[0][1]!.headers as Record<string, string>)["X-CSRF-Token"]).toBe("abc123");
    expect((spy.mock.calls[1][1]!.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });

  it("refreshes once on 401 and retries", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(json(401, { error: { code: "not_authenticated", message: "Please log in." } }))
      .mockResolvedValueOnce(json(200, {}))
      .mockResolvedValueOnce(json(200, { id: "1" }));
    await expect(api("/users/me")).resolves.toEqual({ id: "1" });
    expect(spy.mock.calls.map((c) => c[0])).toEqual(["/api/v1/users/me", "/api/v1/auth/refresh", "/api/v1/users/me"]);
  });

  it("does not refresh for login failures", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(json(401, { error: { code: "invalid_credentials", message: "Nope." } }));
    await expect(api("/auth/login", { method: "POST", body: {} })).rejects.toBeInstanceOf(ApiError);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("surfaces network failures clearly", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fail"));
    await expect(api("/users/me")).rejects.toMatchObject({ code: "network_error" });
  });
});
