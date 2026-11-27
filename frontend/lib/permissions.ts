import type { Permission } from "@/types/api";

/** Ask the browser for location access once (this triggers the prompt). The coordinates are discarded. */
export function requestLocation(): Promise<Permission> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return resolve("DENIED");
    navigator.geolocation.getCurrentPosition(
      () => resolve("GRANTED"),
      (err) => resolve(err.code === err.PERMISSION_DENIED ? "DENIED" : "UNKNOWN"),
      { timeout: 15_000, maximumAge: 60_000 },
    );
  });
}

/** Ask for camera access, then release the camera immediately. */
export async function requestCamera(): Promise<Permission> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    stream.getTracks().forEach((t) => t.stop());
    return "GRANTED";
  } catch (e) {
    return e instanceof DOMException && e.name === "NotAllowedError" ? "DENIED" : "UNKNOWN";
  }
}

/** Current state via the Permissions API, or null where the browser can't say (e.g. Safari for camera). */
export async function queryPermission(name: "geolocation" | "camera"): Promise<Permission | null> {
  try {
    const status = await navigator.permissions.query({ name: name as PermissionName });
    return status.state === "granted" ? "GRANTED" : status.state === "denied" ? "DENIED" : "UNKNOWN";
  } catch {
    return null;
  }
}
