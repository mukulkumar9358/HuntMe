import { z } from "zod";

// Mirrors the backend rules (backend/app/schemas/auth.py); the server remains the authority.
export const usernameSchema = z
  .string()
  .trim()
  .regex(/^[A-Za-z0-9_]{3,24}$/, "Use 3–24 letters, numbers or underscores.");

export const registerSchema = z
  .object({
    username: usernameSchema,
    email: z.string().trim().email("Enter a valid email address."),
    password: z.string().min(10, "Use at least 10 characters.").max(128, "Use 128 characters or fewer."),
    confirmPassword: z.string(),
  })
  .refine((v) => v.password === v.confirmPassword, { path: ["confirmPassword"], message: "Passwords don't match." });

export const loginSchema = z.object({
  identifier: z.string().trim().min(1, "Enter your email or username."),
  password: z.string().min(1, "Enter your password."),
});

export type RegisterValues = z.infer<typeof registerSchema>;
export type LoginValues = z.infer<typeof loginSchema>;

/** Only allow same-site relative redirects (blocks open-redirects like //evil.com). */
export function safeNext(next: string | null | undefined): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : "/";
}
