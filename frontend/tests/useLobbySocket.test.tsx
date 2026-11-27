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
  constructor(public url: string) {
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

describe("lobbySocketUrl", () => {
  it("defaults to the API port on the current host", () => {
    expect(lobbySocketUrl("abc")).toBe(`ws://${window.location.hostname}:8000/ws/rooms/abc`);
  });
});
