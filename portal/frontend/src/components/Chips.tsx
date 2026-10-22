// Status chips the audience can read from the back row: body, deadman, LED, battery, link.
import type { ConnState } from "../ws";
import type { DeadmanState, HeartbeatPayload, LedPayload, PortalEvent, PreflightPayload } from "../types";

export interface ChipsProps {
  body: "car" | "sim" | undefined;
  heartbeat: PortalEvent<HeartbeatPayload> | undefined;
  led: PortalEvent<LedPayload> | undefined;
  preflight: PortalEvent<PreflightPayload> | undefined;
  conn: ConnState;
  compact?: boolean;
}

const DEADMAN_TONE: Record<DeadmanState, string> = { armed: "ok", tripped: "bad", idle: "off" };
const LED_TONE: Record<string, string> = { green: "ok", red: "bad", amber: "warn", blue: "info", off: "off" };
const CONN_TONE: Record<ConnState, string> = { open: "ok", connecting: "warn", closed: "bad" };

export function StatusChips({ body, heartbeat, led, preflight, conn, compact }: ChipsProps) {
  const dm = heartbeat?.payload.state;
  const ledLabel = led?.payload.label ?? "off";
  const battery = preflight?.payload.battery;
  return (
    <div className="chips" aria-label="status">
      <span className={`chip ${body === "car" ? "ok" : body === "sim" ? "info" : "off"}`}><span className="dot" />{body === "car" ? "CAR" : body === "sim" ? "SIM" : "BODY"}{!compact && body && <small>{body === "car" ? "DeepRacer" : "twin"}</small>}</span>
      <span className={`chip ${dm ? DEADMAN_TONE[dm] : "off"}`}><span className="dot" />{dm ?? "deadman"}{!compact && <small>deadman{heartbeat ? ` ${heartbeat.payload.gap_ms} ms` : ""}</small>}</span>
      <span className={`chip ${LED_TONE[ledLabel] ?? "off"}`}><span className="dot" />{ledLabel}<small>LED</small></span>
      <span className={`chip ${battery == null ? "off" : battery >= 3 ? "ok" : "bad"}`}><span className="dot" />{battery == null ? "n/a" : `${battery}/10`}<small>battery</small></span>
      <span className={`chip ${CONN_TONE[conn]}`}><span className="dot" />{conn}{!compact && <small>portal</small>}</span>
    </div>
  );
}
