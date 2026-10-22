import { Panel } from "./Panel";
import s from "./Panel.module.css";
import { fmtTime } from "../ws";
import type { ClientOp, PortalEvent, PreflightPayload } from "../types";

type Row = { label: string; value: string; state: "ok" | "bad" | "na" };

function rows(p: PreflightPayload): Row[] {
  const fmt = (v: number | null | undefined, unit = "") => (v == null ? "n/a" : `${v}${unit}`);
  return [
    { label: "Battery", value: `${p.battery}/10`, state: p.battery >= 3 ? "ok" : "bad" },
    { label: "Camera", value: fmt(p.camera_fps, " fps"), state: p.camera_fps == null ? "na" : p.camera_fps > 0 ? "ok" : "bad" },
    { label: "Link RTT", value: fmt(p.link_rtt_ms, " ms"), state: p.link_rtt_ms == null ? "na" : p.link_rtt_ms < 100 ? "ok" : "bad" },
    { label: "Mode", value: p.mode == null ? "n/a" : p.mode === 0 ? "0 manual" : p.mode === 1 ? "1 autonomous" : "2 calibration", state: p.mode == null ? "na" : p.mode === 0 ? "ok" : "bad" },
    { label: "Enabled", value: p.enabled == null ? "n/a" : String(p.enabled), state: p.enabled == null ? "na" : p.enabled ? "ok" : "bad" },
    { label: "Deadman", value: p.deadman, state: p.deadman === "armed" ? "ok" : p.deadman === "tripped" ? "bad" : "na" },
    { label: "Decider", value: fmt(p.decider_latency_ms, " ms"), state: p.decider_latency_ms == null ? "na" : p.decider_latency_ms < 1500 ? "ok" : "bad" },
    { label: "Calibration", value: p.calibration, state: p.calibration === "ok" ? "ok" : "bad" },
  ];
}

export function Preflight({ preflight, send }: { preflight: PortalEvent<PreflightPayload> | undefined; send: (op: ClientOp) => boolean }) {
  const p = preflight?.payload;
  return (
    <Panel title="Pre-flight" right={<button className={s.small} onClick={() => send({ op: "preflight" })}>Run</button>}>
      {!p && <div className={s.muted}>Not run yet. The rover checks battery, camera, link, mode, deadman, decider and calibration, then speaks go/no-go.</div>}
      {p && (
        <div className={s.pfBody}>
          <div className={`${s.go} ${p.go ? s.goYes : s.goNo}`}>{p.go ? "GO" : "NO GO"}<small>{fmtTime(preflight!.ts)}</small></div>
          <div className={s.pfGrid}>
            {rows(p).map((r) => (
              <div key={r.label} className={s.pfCell}>
                <span className={s.pfLabel}>{r.label}</span>
                <span className={`${s.pfValue} ${s[r.state]}`}>{r.value}</span>
              </div>
            ))}
          </div>
          {p.reasons.length > 0 && <ul className={s.reasons}>{p.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
        </div>
      )}
    </Panel>
  );
}
