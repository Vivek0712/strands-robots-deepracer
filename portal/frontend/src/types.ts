// Event shapes from docs/dev/CONTRACTS.md section 4. The portal renders these and nothing else.
// `connect` is the one addition for the stage portal: the car-connection step log the Settings view
// shows while POST /api/car/connect runs (payload {step, status, detail}).

export type EventType =
  | "thought" | "command" | "verdict" | "approval" | "motion" | "stop" | "heartbeat"
  | "preflight" | "frame" | "voice" | "led" | "body" | "error" | "connect";

export const EVENT_TYPES: EventType[] = [
  "thought", "command", "verdict", "approval", "motion", "stop", "heartbeat",
  "preflight", "frame", "voice", "led", "body", "error", "connect",
];

export type VerdictAction = "Proceed" | "Guide" | "Confirm" | "Deny";

export interface PortalEvent<P = Record<string, unknown>> {
  ts: string;
  seq: number;
  session: string;
  beat: string | null;
  type: EventType;
  source: string;
  payload: P;
}

export interface VerdictPayload {
  request_id: string;
  stage: "envelope" | "frame";
  action: VerdictAction;
  reason: string;
  class: string | null;
  probability: number | null;
  latency_ms: number;
  frame_ref: string | null;
}

export interface CommandPayload {
  tool: string;
  args: Record<string, unknown>;
  request_id: string;
}

export interface ApprovalPayload {
  request_id: string;
  decision: "approved" | "denied" | "timeout";
  by: "operator" | "pregrant";
}

export type StopCause = "trailing_zero" | "operator" | "deny" | "barge_in" | "deadman" | "error";

export interface StopPayload {
  request_id: string | null;
  cause: StopCause;
  latency_ms: number | null;
}

export interface MotionPayload {
  request_id: string;
  state: "start" | "end";
  angle: number;
  throttle: number;
  duration_s: number;
  messages: number;
}

export interface PreflightPayload {
  battery: number;
  camera_fps: number | null;
  link_rtt_ms: number | null;
  mode: number | null;
  enabled: boolean | null;
  deadman: string;
  decider_latency_ms: number | null;
  calibration: "ok" | "uninitialised" | "unknown";
  pwm_outputs?: "ok" | "disabled" | "unknown";
  go: boolean;
  reasons: string[];
}

export interface FramePayload { frame_ref: string; width: number; height: number }
export interface VoicePayload {
  event: "ptt_down" | "ptt_up" | "transcript" | "speech_start" | "speech_end" | "barge_in";
  text: string | null;
  t_ms: number;
}
export type LedLabel = "green" | "red" | "amber" | "blue" | "off";
export interface LedPayload { red: number; green: number; blue: number; label: LedLabel }
export interface BodyPayload { active: "car" | "sim" }
export interface TwinPose { body: "twin"; x: number; y: number; yaw: number; v: number; t_ms: number }
export type DeadmanState = "idle" | "armed" | "tripped";
export interface HeartbeatPayload { state: DeadmanState; gap_ms: number }
export interface ThoughtPayload { text: string }
export interface ErrorPayload { where: string; message: string }
export type ConnectStatus = "running" | "ok" | "fail" | "skip";
export interface ConnectPayload { step: string; status: ConnectStatus; detail: string | null }

export interface PendingApproval { request_id: string; reason: string | null; stage: string | null; ts: string }

export interface VoiceRuntimeStatus {
  state: "off" | "idle" | "starting" | "live" | "error";
  error?: string | null;
  pressed?: boolean;
  listeners?: number;
  stats?: Record<string, unknown> | null;
}

export interface PortalState {
  session: string;
  run_dir: string;
  events: number;
  clients: number;
  latest: Partial<Record<EventType, PortalEvent>>;
  pending_approvals: PendingApproval[];
  body: "car" | "sim";
  runtime: string;
  runtime_status?: Record<string, unknown> & { voice?: VoiceRuntimeStatus; decider_url?: string };
  console_url?: string;
  decider_url?: string;
  safety: string;
  ts: string;
}

export type ServerMessage =
  | { op: "snapshot"; events: PortalEvent[]; state: PortalState }
  | { op: "event"; event: PortalEvent }
  | { op: "ack"; for: string; [k: string]: unknown }
  | { op: "error"; for?: string; reason: string }
  | { op: "pong"; ts: string };

export type ClientOp =
  | { op: "command"; text: string; beat?: string }
  | { op: "approve"; request_id: string; approved: boolean }
  | { op: "stop_all" }
  | { op: "preflight" }
  | { op: "body"; active: "car" | "sim" }
  | { op: "ptt"; state: "down" | "up" }
  | { op: "audio"; pcm_b64: string }
  | { op: "ping" };

// ----- REST contracts (portal/backend/car.py; mounted by app.py) -------------------------------

export type ManeuverShape = "square" | "circle" | "figure_8" | "straight" | "u_turn" | "triangle" | "oval" | "slalom";
export const MANEUVER_SHAPES: ManeuverShape[] = ["square", "circle", "figure_8", "straight", "u_turn", "triangle", "oval", "slalom"];

/** GET /api/car/status: CarService.status() merged with the last CarLink.to_dict(). */
export interface CarStatus {
  connected: boolean;
  host: string | null;
  how: "direct" | "tunnel" | "none" | string;
  busy?: boolean;
  env?: Record<string, string>;
  body?: "car" | "sim";
  ssh_host?: string | null;
  found_by?: string | null;
  rosbridge_port?: number | null;
  console_url?: string | null;
  rtt_ms?: number | null;
  error?: string | null;
  runtime_status?: { deadman?: string | null; battery?: number | null; session?: string | null; armed?: boolean; voice?: VoiceRuntimeStatus } & Record<string, unknown>;
  // the brief's nested shape, honoured if the backend ever sends it
  rosbridge?: { connected: boolean; rtt_ms: number | null } | null;
  console?: { ok: boolean; fps: number | null } | null;
  battery?: number | null;
  deadman?: string | null;
  session?: string | null;
}
/** GET/POST /api/car/settings; POST answers {accepted, host, mac, mdns}. */
export interface CarSettings { host: string | null; mac: string | null; mdns: string | null; accepted?: boolean }
/** POST /api/car/wifi-usb {ssid, password} -> 200 {accepted, written: [volume]} | 409/422 {accepted: false, reason}. */
export interface WifiUsbWriteResult { accepted: boolean; written?: string[]; reason?: string | null }
/** GET /api/car/wifi-usb -> {volumes: [path], reports: {volume: device-status.txt text}}. */
export interface WifiUsbReport { volumes: string[]; reports: Record<string, string> }
/** GET /api/memory -> {operator_name, facts, updated}; POST {name} | {forget: true} -> {accepted, operator_name, ...}. */
export interface MemoryPayload { operator_name: string | null; facts?: Record<string, unknown>; updated?: string | null; accepted?: boolean }
/** POST /api/show/maneuver {shape, size_m} and /api/show/say {text} -> {accepted, request_id}. */
export interface ShowAccepted { accepted: boolean; request_id?: string; reason?: string; [k: string]: unknown }

export const SAFETY_LINE = "Physics stops the car; the decider explains.";
export const SAFETY_DETAIL = "Pen, hop cap, on-car deadman and the marshal's thumb stop the car; this screen only shows why.";
