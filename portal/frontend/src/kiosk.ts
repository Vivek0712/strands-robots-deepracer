// The two booth kiosks talk HTTP to the portal (POST /kiosk/judge, /kiosk/simon, GET/POST /kiosk/labels,
// GET /kiosk/leaderboard). Shapes mirror beats/kiosk.py; the WebSocket keeps carrying the same verdicts
// to the audit. Physics stops the car; the decider explains; the kiosks are the decider explaining all day.

import type { VerdictAction } from "./types";

export interface EgressEntry { what: string; host: string; ms: number | null }

export interface LabelInfo { label: string; description: string | null; builtin: boolean }
export interface LabelsPayload { labels: LabelInfo[]; count: number; max: number }

export interface JudgeResult {
  accepted: boolean;
  request_id: string;
  ts: string;
  nickname: string;
  expected: string | null;
  labels: string[];
  consent: boolean;
  frame_saved: boolean;
  frame_ref: string | null;
  action: VerdictAction;
  reason: string;
  class: string | null;
  probability: number | null;
  latency_ms: number | null;
  probabilities: Record<string, number>;
  caption: string | null;
  error: string | null;
  wrong: boolean;
  fool_score: number;
  egress: EgressEntry[];
  session?: string;
}

export interface LeaderboardEntry {
  rank: number;
  tries: number;
  nickname: string;
  class: string | null;
  probability: number | null;
  latency_ms: number | null;
  expected: string | null;
  consent: boolean;
  frame_ref: string | null;
  ts: string;
  wrong: boolean;
  fool_score: number;
}
export interface LeaderboardPayload { session: string; entries: LeaderboardEntry[]; total: number; recent: JudgeResult[] }

export interface StagePayload {
  request_id: string; stage: "envelope" | "frame"; action: VerdictAction; reason: string;
  class: string | null; probability: number | null; latency_ms: number; frame_ref: string | null;
}
export interface DriveArgs { linear: number; angular: number; duration: number }
export interface SimonResult {
  accepted: boolean;
  text: string;
  ts: string;
  request_id: string | null;
  command: DriveArgs | null;
  action: VerdictAction | null;
  reason: string;
  card: string;
  latency_ms: number | null;
  class: string | null;
  probability: number | null;
  stages: StagePayload[];
  replan: DriveArgs | null;
  egress: EgressEntry[];
  egress_note: string;
  envelope?: { max_linear: number; max_duration_s: number; allowed_directions: string[]; max_angular: number };
}
export interface SimonHistoryPayload { session: string; history: SimonResult[] }

export class KioskError extends Error {
  constructor(message: string, public status: number, public body: Record<string, unknown>) { super(message); }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  let data: Record<string, unknown> = {};
  try { data = (await r.json()) as Record<string, unknown>; } catch { /* no body */ }
  if (!r.ok) throw new KioskError(String(data.reason ?? data.error ?? `HTTP ${r.status}`), r.status, data);
  return data as unknown as T;
}

export function getJson<T>(url: string): Promise<T> { return request<T>(url); }
export function postJson<T>(url: string, body: unknown): Promise<T> {
  return request<T>(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export function fmtP(p: number | null | undefined): string { return p == null ? "—" : p.toFixed(2); }
export function fmtMs(ms: number | null | undefined): string { return ms == null ? "— ms" : `${ms} ms`; }
export function fmtPlan(a: DriveArgs): string {
  const dir = a.linear < 0 ? "back" : "forward";
  const turn = a.angular > 0 ? ", turning left" : a.angular < 0 ? ", turning right" : "";
  return `${dir} at ${Math.abs(a.linear)} m/s for ${a.duration} s${turn}`;
}
