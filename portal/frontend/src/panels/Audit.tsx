import { Panel } from "./Panel";
import s from "./Panel.module.css";
import { fmtTime, frameUrl } from "../ws";
import type { ApprovalPayload, CommandPayload, FramePayload, MotionPayload, PortalEvent, StopPayload, VerdictPayload, VoicePayload } from "../types";

const KINDS = new Set(["command", "verdict", "approval", "stop", "frame", "motion", "voice", "error", "connect"]);

function describe(ev: PortalEvent): { head: string; text: string; frame: string | null; cls?: string } {
  const p = ev.payload as unknown;
  switch (ev.type) {
    case "command": {
      const c = p as CommandPayload;
      const args = Object.entries(c.args ?? {}).map(([k, v]) => `${k}=${String(v)}`).join(", ");
      return { head: c.tool, text: args, frame: null };
    }
    case "verdict": {
      const v = p as VerdictPayload;
      return { head: `${v.action} · ${v.stage}`, text: `${v.reason}${v.class ? ` [${v.class}${v.probability != null ? ` p=${v.probability.toFixed(2)}` : ""}]` : ""} · ${v.latency_ms} ms`, frame: v.frame_ref, cls: v.action };
    }
    case "approval": {
      const a = p as ApprovalPayload;
      return { head: a.decision, text: `by ${a.by} · ${a.request_id}`, frame: null };
    }
    case "stop": {
      const st = p as StopPayload;
      return { head: `stop · ${st.cause}`, text: st.latency_ms != null ? `${st.latency_ms} ms` : "", frame: null };
    }
    case "frame": {
      const f = p as FramePayload;
      return { head: "frame", text: `${f.width}x${f.height}`, frame: f.frame_ref };
    }
    case "motion": {
      const m = p as MotionPayload;
      return { head: `motion ${m.state}`, text: `angle ${m.angle.toFixed(2)} throttle ${m.throttle.toFixed(2)} · ${m.duration_s}s · ${m.messages} msgs`, frame: null };
    }
    case "voice": {
      const v = p as VoicePayload;
      return { head: v.event, text: v.text ?? `${v.t_ms} ms`, frame: null };
    }
    case "thought":
      return { head: "thought", text: String((p as { text?: string }).text ?? ""), frame: null };
    case "heartbeat": {
      const h = p as { state?: string; gap_ms?: number };
      return { head: `deadman ${h.state ?? ""}`, text: `${h.gap_ms ?? "—"} ms gap`, frame: null };
    }
    case "led":
      return { head: `LED ${(p as { label?: string }).label ?? ""}`, text: "", frame: null };
    case "preflight": {
      const f = p as { go?: boolean; battery?: number; reasons?: string[] };
      return { head: f.go ? "GO" : "NO GO", text: `battery ${f.battery ?? "—"}/10${f.reasons?.length ? ` · ${f.reasons.join("; ")}` : ""}`, frame: null, cls: f.go ? "Proceed" : "Deny" };
    }
    case "body": {
      const b = p as { active?: string; body?: string; x?: number; y?: number; v?: number };
      if (b.body === "twin") return { head: "twin pose", text: `x ${b.x?.toFixed(2)} y ${b.y?.toFixed(2)} v ${b.v?.toFixed(2)}`, frame: null };
      return { head: `body ${b.active ?? ""}`, text: "", frame: null };
    }
    case "connect": {
      const c = p as { step?: string; status?: string; detail?: string | null };
      return { head: `${c.step ?? "step"} · ${c.status ?? ""}`, text: c.detail ?? "", frame: null, cls: c.status === "fail" ? "Deny" : c.status === "ok" ? "Proceed" : undefined };
    }
    default: {
      const e = p as { where?: string; message?: string };
      return { head: e.where ?? ev.type, text: e.message ?? JSON.stringify(p), frame: null };
    }
  }
}

export function Audit({ events, session, limit = 60, only }: { events: PortalEvent[]; session?: string; limit?: number; only?: Set<string> }) {
  const kinds = only ?? KINDS;
  const rows = events.filter((e) => kinds.has(e.type)).slice(-limit).reverse();
  return (
    <Panel title="Audit" right={<span className={s.muted}>{rows.length} of {events.length}</span>}>
      <div className={s.auditList}>
        {rows.length === 0 && <div className={s.muted}>No events yet. Send a command or run pre-flight.</div>}
        {rows.map((ev) => {
          const d = describe(ev);
          const url = frameUrl(session ?? ev.session, d.frame);
          return (
            <article key={`${ev.session}-${ev.seq}`} className={`${s.card} ${s["k_" + ev.type] ?? ""}`}>
              <div className={s.cardHead}>
                <span className={s.cardKind}>{ev.type}</span>
                <span className={d.cls ? s[d.cls] : undefined}>{d.head}</span>
              </div>
              <span className={s.cardTime}>#{ev.seq} {fmtTime(ev.ts)}</span>
              <div className={s.cardText}>{d.text}</div>
              {url && <img className={s.thumb} src={url} alt="frame" loading="lazy" />}
            </article>
          );
        })}
      </div>
    </Panel>
  );
}
