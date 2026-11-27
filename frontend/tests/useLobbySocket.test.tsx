import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";

import { lobbySocketUrl, useLobbySocket } from "@/hooks/useLobbySocket";

class FakeSocket {
  static instances: FakeSocket[] = [];
  static OPEN = 1;
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  constructor(public url: string, public protocols?: string[]) {
    FakeSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.onclose?.({ code: 1000 });
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
}

let client: QueryClient;
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeSocket);
  client = new QueryClient();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("useLobbySocket", () => {
  it("connects to the room socket and reports connection state", () => {
    const { result } = renderHook(() => useLobbySocket("room-1"), { wrapper });
    expect(FakeSocket.instances[0].url).toMatch(/\/ws\/rooms\/room-1$/);
    expect(result.current.connected).toBe(false);
    act(() => FakeSocket.instances[0].open());
    expect(result.current.connected).toBe(true);
  });

  it("refetches the room when told it changed, and ignores junk", () => {
    const spy = vi.spyOn(client, "invalidateQueries");
    renderHook(() => useLobbySocket("room-1"), { wrapper });
    const s = FakeSocket.instances[0];
    act(() => s.open());
    spy.mockClear();
    act(() => s.onmessage?.({ data: "not json" }));
    act(() => s.onmessage?.({ data: JSON.stringify({ type: "pong" }) }));
    expect(spy).not.toHaveBeenCalled();
    act(() => s.onmessage?.({ data: JSON.stringify({ type: "room:updated", version: 1 }) }));
    expect(spy).toHaveBeenCalledWith({ queryKey: ["room", "room-1"] });
  });

  it("sends heartbeats", () => {
    renderHook(() => useLobbySocket("room-1"), { wrapper });
    const s = FakeSocket.instances[0];
    act(() => s.open());
    act(() => void vi.advanceTimersByTime(15_000));
    expect(s.sent).toEqual([JSON.stringify({ type: "ping" })]);
  });

  it("reconnects with backoff after an abnormal close", () => {
    renderHook(() => useLobbySocket("room-1"), { wrapper });
    act(() => FakeSocket.instances[0].onclose?.({ code: 1006 }));
    expect(FakeSocket.instances).toHaveLength(1);
    act(() => void vi.advanceTimersByTime(1000));
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it.each([4401, 4403, 4000])("does not reconnect after fatal close code %i", (code) => {
    renderHook(() => useLobbySocket("room-1"), { wrapper });
    act(() => FakeSocket.instances[0].onclose?.({ code }));
    act(() => void vi.advanceTimersByTime(60_000));
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("stays closed after unmount", () => {
    const { unmount } = renderHook(() => useLobbySocket("room-1"), { wrapper });
    unmount();
    act(() => void vi.advanceTimersByTime(60_000));
    expect(FakeSocket.instances).toHaveLength(1);
  });
});

describe("useLobbySocket with a cross-host API (production)", () => {
  const ticketResponse = () =>
    new Response(JSON.stringify({ ticket: "tkt123", expires_in: 30 }), { status: 200, headers: { "Content-Type": "application/json" } });

  it("fetches a single-use ticket and offers it as a subprotocol, never in the URL", async () => {
    vi.stubEnv("NEXT_PUBLIC_WS_URL", "wss://api.other.example");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async () => ticketResponse());
    renderHook(() => useLobbySocket("room-1"), { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetchSpy).toHaveBeenCalledWith("/api/v1/rooms/room-1/ws-ticket", expect.objectContaining({ method: "POST" }));
    expect(FakeSocket.instances).toHaveLength(1);
    expect(FakeSocket.instances[0].url).toBe("wss://api.other.example/ws/rooms/room-1");
    expect(FakeSocket.instances[0].protocols).toEqual(["huntme.ticket", "tkt123"]);
  });

  it("gets a fresh ticket on every reconnect", async () => {
    vi.stubEnv("NEXT_PUBLIC_WS_URL", "wss://api.other.example");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async () => ticketResponse());
    renderHook(() => useLobbySocket("room-1"), { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    act(() => FakeSocket.instances[0].onclose?.({ code: 1006 }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("stops retrying when the ticket is refused (not a member / logged out)", async () => {
    vi.stubEnv("NEXT_PUBLIC_WS_URL", "wss://api.other.example");
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () => new Response(JSON.stringify({ error: { code: "room_not_found", message: "Room not found." } }), { status: 404 }),
    );
    renderHook(() => useLobbySocket("room-1"), { wrapper });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(FakeSocket.instances).toHaveLength(0);
  });
});

describe("lobbySocketUrl", () => {
  it("defaults to the API port on the current host", () => {
    expect(lobbySocketUrl("abc")).toBe(`ws://${window.location.hostname}:8000/ws/rooms/abc`);
  });
});
