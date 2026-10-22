// Reconnecting WebSocket client + a React store of the run. One socket per page; the backend
// replays the last 200 events on every (re)connect, so a reconnect simply replaces the list.

import { useEffect, useMemo, useReducer, useRef } from "react";
import type { ClientOp, EventType, PendingApproval, PortalEvent, PortalState, ServerMessage, VerdictPayload } from "./types";

const MAX_EVENTS = 400;

export type ConnState = "connecting" | "open" | "closed";

export interface RunStore {
  conn: ConnState;
  events: PortalEvent[];
  latest: Partial<Record<EventType, PortalEvent>>;
  pending: PendingApproval[];
  state: PortalState | null;
  lastError: string | null;
  acks: Record<string, unknown>[];
}

type Action =
  | { kind: "conn"; conn: ConnState }
  | { kind: "snapshot"; events: PortalEvent[]; state: PortalState }
  | { kind: "event"; event: PortalEvent }
  | { kind: "ack"; ack: Record<string, unknown> }
  | { kind: "error"; reason: string };

const initial: RunStore = { conn: "connecting", events: [], latest: {}, pending: [], state: null, lastError: null, acks: [] };

function trackPending(pending: PendingApproval[], ev: PortalEvent): PendingApproval[] {
  const p = ev.payload as Record<string, unknown>;
  const rid = typeof p.request_id === "string" ? p.request_id : null;
  if (!rid) return pending;
  if (ev.type === "verdict" && (p as unknown as VerdictPayload).action === "Confirm") {
    if (pending.some((x) => x.request_id === rid)) return pending;
    return [...pending, { request_id: rid, reason: String(p.reason ?? ""), stage: String(p.stage ?? ""), ts: ev.ts }];
  }
  if (ev.type === "approval" || ev.type === "stop") return pending.filter((x) => x.request_id !== rid);
  return pending;
}

function reducer(s: RunStore, a: Action): RunStore {
  switch (a.kind) {
    case "conn":
      return { ...s, conn: a.conn };
    case "snapshot": {
      const latest: RunStore["latest"] = {};
      let pending: PendingApproval[] = [];
      for (const ev of a.events) {
        latest[ev.type] = ev;
        pending = trackPending(pending, ev);
      }
      return { ...s, events: a.events.slice(-MAX_EVENTS), latest, pending, state: a.state, lastError: null };
    }
    case "event": {
      const events = s.events.length >= MAX_EVENTS ? [...s.events.slice(1), a.event] : [...s.events, a.event];
      const latest = { ...s.latest, [a.event.type]: a.event };
      const pending = trackPending(s.pending, a.event);
      let state = s.state;
      const active = (a.event.payload as { active?: unknown }).active; // the twin's pose samples are `body` events too
      if (a.event.type === "body" && state && (active === "car" || active === "sim")) state = { ...state, body: active };
      return { ...s, events, latest, pending, state };
    }
    case "ack":
      return { ...s, acks: [...s.acks.slice(-19), a.ack], lastError: null };
    case "error":
      return { ...s, lastError: a.reason };
  }
}

export function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const host = location.host || "127.0.0.1:8765";
  return `${proto}://${host}/ws`;
}

export class ReconnectingSocket {
  private ws: WebSocket | null = null;
  private delay = 500;
  private closed = false;
  private timer: number | null = null;
  constructor(private url: string, private onMessage: (m: ServerMessage) => void, private onConn: (c: ConnState) => void) {
    this.connect();
  }
  private connect() {
    if (this.closed) return;
    this.onConn("connecting");
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => { this.delay = 500; this.onConn("open"); };
    ws.onmessage = (e) => { try { this.onMessage(JSON.parse(e.data) as ServerMessage); } catch { /* ignore */ } };
    ws.onclose = () => { this.onConn("closed"); this.schedule(); };
    ws.onerror = () => { ws.close(); };
  }
  private schedule() {
    if (this.closed || this.timer !== null) return;
    this.timer = window.setTimeout(() => { this.timer = null; this.connect(); }, this.delay);
    this.delay = Math.min(this.delay * 2, 5000);
  }
  send(op: ClientOp): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) { this.ws.send(JSON.stringify(op)); return true; }
    return false;
  }
  close() { this.closed = true; if (this.timer) window.clearTimeout(this.timer); this.ws?.close(); }
}

export function usePortal(): { store: RunStore; send: (op: ClientOp) => boolean } {
  const [store, dispatch] = useReducer(reducer, initial);
  const sockRef = useRef<ReconnectingSocket | null>(null);
  useEffect(() => {
    const sock = new ReconnectingSocket(
      wsUrl(),
      (m) => {
        if (m.op === "snapshot") dispatch({ kind: "snapshot", events: m.events, state: m.state });
        else if (m.op === "event") dispatch({ kind: "event", event: m.event });
        else if (m.op === "ack") dispatch({ kind: "ack", ack: m });
        else if (m.op === "error") dispatch({ kind: "error", reason: m.reason });
      },
      (conn) => dispatch({ kind: "conn", conn }),
    );
    sockRef.current = sock;
    return () => sock.close();
  }, []);
  const send = useMemo(() => (op: ClientOp) => sockRef.current?.send(op) ?? false, []);
  return { store, send };
}

export function frameUrl(session: string | undefined, frameRef: string | null | undefined): string | null {
  if (!session || !frameRef) return null;
  const name = frameRef.split("/").pop();
  if (!name) return null;
  return `/api/runs/${encodeURIComponent(session)}/frames/${encodeURIComponent(name)}`;
}

export function fmtTime(ts: string): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleTimeString([], { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}
