import { loginSchema, registerSchema, safeNext } from "@/lib/validation";

const valid = { username: "Mukul_01", email: "m@example.com", password: "correct-horse-battery", confirmPassword: "correct-horse-battery" };

describe("registerSchema", () => {
  it("accepts valid input", () => expect(registerSchema.safeParse(valid).success).toBe(true));
  it.each([
    [{ username: "ab" }, "username"],
    [{ username: "has space" }, "username"],
    [{ email: "nope" }, "email"],
    [{ password: "short", confirmPassword: "short" }, "password"],
    [{ confirmPassword: "different-password" }, "confirmPassword"],
  ])("rejects %j", (patch, field) => {
    const r = registerSchema.safeParse({ ...valid, ...patch });
    expect(r.success).toBe(false);
    expect(r.error?.issues.some((i) => i.path[0] === field)).toBe(true);
  });
});

describe("loginSchema", () => {
  it("requires both fields", () => expect(loginSchema.safeParse({ identifier: "", password: "" }).success).toBe(false));
});

describe("safeNext", () => {
  it.each([
    ["/create-room", "/create-room"],
    [null, "/"],
    ["https://evil.com", "/"],
    ["//evil.com", "/"],
    ["/\\evil.com", "/"],
  ])("%s -> %s", (input, out) => expect(safeNext(input)).toBe(out));
});
