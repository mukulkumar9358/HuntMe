"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { roomKey } from "@/hooks/useRooms";
import { ApiError, api } from "@/services/api";

const PING_MS = 15_000;
const MAX_BACKOFF_MS = 15_000;
// Server close codes that mean "don't retry": unauthorised, not a member, removed from room.
const FATAL_CLOSE_CODES = new Set([4401, 4403, 4000]);

/**
 * WebSocket origin. Next.js rewrites can't proxy WebSockets reliably, so the browser connects to the API directly.
 * Set NEXT_PUBLIC_WS_URL at build time (e.g. wss://api.example.com). Locally it defaults to the API on :8000.
 */
export function lobbySocketUrl(roomId: string): string {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  let base = configured;
  if (!base) {
    const { protocol, hostname, host } = window.location;
    base = protocol === "https:" ? `wss://${host}` : `ws://${hostname}:8000`;
  }
  return `${base.replace(/\/$/, "")}/ws/rooms/${roomId}`;
}

/**
 * True when the socket host differs from the page host (production: frontend and API live on different
 * hostnames), so the browser won't send our auth cookies to it. In that case we authenticate with a
 * single-use ticket minted through the same-origin API. Locally (same hostname) the cookie path is used.
 */
function needsTicket(): boolean {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  if (!configured) return false;
  try {
    return new URL(configured).hostname !== window.location.hostname;
  } catch {
    return false;
  }
}

const TICKET_SUBPROTOCOL = "huntme.ticket";

/** Keeps a lobby socket open. Returns whether it's connected; while it isn't, callers should poll. */
export function useLobbySocket(roomId: string, enabled = true): { connected: boolean } {
  const qc = useQueryClient();
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let socket: WebSocket | null = null;
    let pingTimer: ReturnType<typeof setInterval> | undefined;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let disposed = false;

    // Function declarations (hoisted) so these can reference each other regardless of order.
    function scheduleRetry() {
      retryTimer = setTimeout(connect, Math.min(1000 * 2 ** attempt++, MAX_BACKOFF_MS));
    }

    function open(protocols?: string[]) {
      const url = lobbySocketUrl(roomId);
      socket = protocols ? new WebSocket(url, protocols) : new WebSocket(url);
      socket.onopen = () => {
        attempt = 0;
        setConnected(true);
        pingTimer = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send(JSON.stringify({ type: "ping" })), PING_MS);
        // Catch up on anything missed while disconnected.
        void qc.invalidateQueries({ queryKey: roomKey(roomId) });
      };
      socket.onmessage = (event) => {
        try {
          if (JSON.parse(String(event.data)).type === "room:updated") void qc.invalidateQueries({ queryKey: roomKey(roomId) });
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = (event) => {
        clearInterval(pingTimer);
        setConnected(false);
        if (disposed) return;
        void qc.invalidateQueries({ queryKey: roomKey(roomId) }); // e.g. removed from the room -> 404 -> UI reacts
        if (FATAL_CLOSE_CODES.has(event.code)) return;
        scheduleRetry();
      };
    }

    // A fresh ticket is fetched for every (re)connect: tickets are single-use and expire in seconds.
    async function connectWithTicket() {
      try {
        const { ticket } = await api<{ ticket: string }>(`/rooms/${roomId}/ws-ticket`, { method: "POST" });
        if (!disposed) open([TICKET_SUBPROTOCOL, ticket]);
      } catch (err) {
        if (disposed) return;
        if (err instanceof ApiError && [401, 403, 404].includes(err.status)) {
          void qc.invalidateQueries({ queryKey: roomKey(roomId) }); // logged out / removed: let the UI react, don't retry
          return;
        }
        scheduleRetry(); // network blip or API waking from sleep
      }
    }

    function connect() {
      if (needsTicket()) void connectWithTicket();
      else open();
    }

    connect();
    return () => {
      disposed = true;
      clearInterval(pingTimer);
      clearTimeout(retryTimer);
      socket?.close();
      setConnected(false);
    };
  }, [roomId, enabled, qc]);

  return { connected };
}
