// OPERATOR: the speaker's laptop between beats. One big button per act of the show, the live audit
// with a type filter, approvals, and every operator op the backend accepts (command, approve,
// stop_all, preflight, body, ptt). The acts call the show routes; a missing route reads as
// "not available" instead of breaking the view. Physics stops the car; the decider explains.

import { Fragment, useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import s from "./Operator.module.css";
import { apiGet, apiPost, errText } from "../api";
import type { ApiResult } from "../api";
import type { RunStore } from "../ws";
import { MANEUVER_SHAPES, EVENT_TYPES, SAFETY_LINE } from "../types";
import type { ClientOp, EventType, LedLabel, ManeuverShape, MemoryPayload, PortalEvent, PreflightPayload, ShowAccepted } from "../types";
import { Audit } from "../panels/Audit";
import { Preflight } from "../panels/Preflight";
import { PttButton } from "../components/Ptt";
import type { PttState } from "../usePtt";

type Toast = { tone: "ok" | "err" | ""; text: string };
const LEDS: LedLabel[] = ["green", "red", "amber", "blue", "off"];
const quiet: Toast = { tone: "", text: "" };

type GateMode = "enforce" | "advisory" | "off";
const GATE_HINT: Record<GateMode, string> = {
  enforce: "a Deny stops the hop (the three vision beats)",
  advisory: "the decider is asked and shown; the hop proceeds; caps and deadman stand",
  off: "no decider questions; speed caps and the deadman stand",
};

function toastOf<T>(r: ApiResult<T>, okText: (d: T) => string): Toast {
  const e = errText(r);
  if (e) return { tone: "err", text: e };
  return { tone: "ok", text: r.ok ? okText(r.data) : "" };
}

function Act({ n, name, children, right, hint }: { n: string; name: string; children: ReactNode; right?: ReactNode; hint?: boolean }) {
  return (
    <section className={`${s.card} ${s.act} ${hint ? s.hintCard : ""}`}>
      <div className={s.actHead}><span className={s.actName}>{name}</span><span className={s.actNo}>{right ?? n}</span></div>
      {children}
    </section>
  );
}

function ToastLine({ t }: { t: Toast }) { return <div className={`toast ${t.tone}`}>{t.text}</div>; }

function flatten(obj: unknown, prefix = ""): [string, string][] {
  if (obj === null || typeof obj !== "object") return [[prefix || "value", String(obj)]];
  const out: [string, string][] = [];
  for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === "object" && !Array.isArray(v)) out.push(...flatten(v, key));
    else out.push([key, Array.isArray(v) ? v.join(", ") : String(v)]);
  }
  return out;
}

export interface OperatorProps {
  store: RunStore;
  send: (op: ClientOp) => boolean;
  pttHeld: boolean;
  ptt: PttState;
}

export function Operator({ store, send, pttHeld, ptt }: OperatorProps) {
  const session = store.state?.session;
  const body = store.state?.body;
  const preflight = store.latest.preflight as PortalEvent<PreflightPayload> | undefined;
  const lastAck = store.acks[store.acks.length - 1];

  // Maneuver
  const [shape, setShape] = useState<ManeuverShape>("square");
  const [size, setSize] = useState("0.6");
  const [manT, setManT] = useState<Toast>(quiet);
  const maneuver = async () => {
    const size_m = Number(size);
    if (!Number.isFinite(size_m) || size_m <= 0) { setManT({ tone: "err", text: "size must be a positive number of metres" }); return; }
    setManT({ tone: "", text: "sending…" });
    setManT(toastOf(await apiPost<ShowAccepted>("/api/show/maneuver", { shape, size_m }), (d) => `${shape} ${size_m} m${d?.request_id ? ` · ${d.request_id}` : ""}`));
  };

  // Talk
  const [talk, setTalk] = useState("");
  const [talkT, setTalkT] = useState<Toast>(quiet);
  const sendTalk = (e: FormEvent) => {
    e.preventDefault();
    const t = talk.trim();
    if (!t) return;
    setTalkT(send({ op: "command", text: t }) ? { tone: "ok", text: `sent "${t}"` } : { tone: "err", text: "portal socket closed" });
    setTalk("");
  };

  // LED
  const [ledT, setLedT] = useState<Toast>(quiet);
  const led = async (label: LedLabel) => setLedT(toastOf(await apiPost<unknown>("/api/show/led", { label }), () => `LED ${label}`));

  // Metrics
  const [metT, setMetT] = useState<Toast>(quiet);
  const [metrics, setMetrics] = useState<unknown>(null);
  const sayMetrics = async () => setMetT(toastOf(await apiPost<ShowAccepted>("/api/show/say", { text: "Tell me your metrics" }), (d) => `asked aloud${d?.request_id ? ` · ${d.request_id}` : ""}`));
  const fetchMetrics = async () => {
    const r = await apiGet<unknown>("/api/show/metrics");
    setMetT(toastOf(r, () => "fetched"));
    setMetrics(r.ok ? r.data : null);
  };

  // Memory
  const [memory, setMemory] = useState<ApiResult<MemoryPayload> | null>(null);
  const [memName, setMemName] = useState("");
  const [memT, setMemT] = useState<Toast>(quiet);
  const [gateMode, setGateMode] = useState<GateMode | null>(null);
  const [gateT, setGateT] = useState<Toast | null>(null);
  const loadGate = useCallback(async () => {
    const r = await apiGet<{ mode: GateMode; present: boolean }>("/api/show/gate");
    setGateMode(r.ok && r.data ? r.data.mode : null);
  }, []);
  useEffect(() => { void loadGate(); }, [loadGate]);
  const setGate = async (mode: GateMode) => {
    const r = await apiPost<{ accepted: boolean; mode: GateMode }>("/api/show/gate", { mode });
    if (r.ok && r.data) setGateMode(r.data.mode);
    setGateT(toastOf(r, (d) => `gate ${d?.mode ?? mode}`));
  };
  const [throttle, setThrottle] = useState<number | null>(null);
  const [throttleDraft, setThrottleDraft] = useState<string>("");
  const [thrT, setThrT] = useState<Toast | null>(null);
  const loadThrottle = useCallback(async () => {
    const r = await apiGet<{ present: boolean; throttle_at_max_speed?: number }>("/api/show/throttle");
    const v = r.ok && r.data?.present ? r.data.throttle_at_max_speed ?? null : null;
    setThrottle(v);
    if (v !== null) setThrottleDraft(String(v));
  }, []);
  useEffect(() => { void loadThrottle(); }, [loadThrottle]);
  const applyThrottle = async () => {
    const v = Number(throttleDraft);
    const r = await apiPost<{ accepted: boolean; throttle_at_max_speed: number; saved: string }>("/api/show/throttle", { throttle_at_max_speed: v });
    if (r.ok && r.data) setThrottle(r.data.throttle_at_max_speed);
    setThrT(toastOf(r, (d) => `hop throttle ${d?.throttle_at_max_speed ?? v} · ${d?.saved ?? ""}`));
  };
  const testHop = async () => setThrT(toastOf(await apiPost<ShowAccepted>("/api/show/say", { text: "Hop forward twenty centimetres." }), () => "test hop asked"));
  const loadMemory = useCallback(async () => setMemory(await apiGet<MemoryPayload>("/api/memory")), []);
  useEffect(() => { void loadMemory(); }, [loadMemory]);
  const saveMemory = async (e: FormEvent) => {
    e.preventDefault();
    const name = memName.trim();
    if (!name) return;
    const r = await apiPost<MemoryPayload>("/api/memory", { name });
    setMemT(toastOf(r, (d) => `remembered ${d?.operator_name ?? name}`));
    if (r.ok) { setMemName(""); void loadMemory(); }
  };
  const forget = async () => {
    const r = await apiPost<MemoryPayload>("/api/memory", { forget: true });
    setMemT(toastOf(r, () => "forgotten"));
    if (r.ok) void loadMemory();
  };

  // Audit filter
  const [filter, setFilter] = useState<EventType | "all">("all");
  // "all" leaves out the 2 Hz heartbeat and the 10 Hz twin poses; their chips show them on their own.
  const only = filter === "all" ? new Set<string>(EVENT_TYPES.filter((t) => t !== "heartbeat" && t !== "body")) : new Set<string>([filter]);

  return (
    <>
      <main className={s.grid}>
        <div className={s.col} aria-label="show">
          <Act n="1" name="Pre-flight" right={preflight ? <span className={preflight.payload.go ? "Proceed" : "Deny"}>{preflight.payload.go ? "GO" : "NO GO"}</span> : undefined}>
            <button className={s.big} onClick={() => send({ op: "preflight" })}>Run pre-flight</button>
            <div className="hint">Battery, camera, link, mode, deadman, decider, calibration; the rover speaks go / no-go.</div>
          </Act>

          <Act n="2" name="Maneuver">
            <div className={s.shapes}>
              {MANEUVER_SHAPES.map((sh) => <button key={sh} className={shape === sh ? s.on : ""} onClick={() => setShape(sh)}>{sh.replace("_", " ")}</button>)}
            </div>
            <div className={s.row}>
              <label className="label" htmlFor="size-m">size (m)</label>
              <input id="size-m" value={size} onChange={(e) => setSize(e.target.value)} inputMode="decimal" style={{ maxWidth: 120 }} />
              <button className={`${s.big} btnPrimary`} style={{ flex: 2, width: "auto" }} onClick={maneuver}>Drive {shape.replace("_", " ")}</button>
            </div>
            <ToastLine t={manT} />
          </Act>

          <Act n="3" name="Talk">
            <form className={s.cmd} onSubmit={sendTalk}>
              <input value={talk} onChange={(e) => setTalk(e.target.value)} placeholder="go forward 20 cm / what do you see?" aria-label="command text" data-cmd-input />
              <button type="submit" className="btnPrimary">Send</button>
            </form>
            <ToastLine t={talkT} />
          </Act>

          <Act n="4" name="LED">
            <div className={s.leds}>{LEDS.map((l) => <button key={l} className={s["led" + l]} onClick={() => led(l)}>{l}</button>)}</div>
            <ToastLine t={ledT} />
          </Act>

          <Act n="5" name="Metrics">
            <div className={s.row}>
              <button className={s.big} style={{ flex: 1, width: "auto" }} onClick={sayMetrics}>Ask: "Tell me your metrics"</button>
              <button className={s.big} style={{ flex: 1, width: "auto" }} onClick={fetchMetrics}>Fetch metrics</button>
            </div>
            {metrics != null && (
              <dl className={s.kv}>{flatten(metrics).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd>{v}</dd></Fragment>)}</dl>
            )}
            <ToastLine t={metT} />
          </Act>

          <Act n="6" name="Memory" right={<button className="btnQuiet" onClick={() => void loadMemory()}>refresh</button>}>
            <div className={s.name}>{memory?.ok ? (memory.data?.operator_name ?? <span className="dim">nobody remembered yet</span>) : <span className="dim">{errText(memory) ?? "loading…"}</span>}</div>
            {memory?.ok && memory.data?.updated && <div className="hint">remembered {memory.data.updated}{memory.data.facts && Object.keys(memory.data.facts).length ? ` · ${Object.keys(memory.data.facts).length} fact(s)` : ""}</div>}
            <form className={s.row} onSubmit={saveMemory}>
              <input value={memName} onChange={(e) => setMemName(e.target.value)} placeholder="name to remember" aria-label="name to remember" />
              <button type="submit" className="btnPrimary">Remember</button>
              <button type="button" className="btnQuiet" onClick={forget} disabled={!memory?.ok || !memory.data?.operator_name}>Forget</button>
            </form>
            <ToastLine t={memT} />
          </Act>

          <Act n="7" name="Blindfold" hint right="gate">
            <div className={s.hintText}>Cover the lens, then ask for a hop. The frame question returns no scene and the gate answers Deny; the stage shows the frozen frame and the stamp.</div>
          </Act>
          <Act n="8" name="Foot" hint right="gate">
            <div className={s.hintText}>Step a foot into the frame during any hop. The person question flips the merge toward Deny; the car stops on physics, the decider explains.</div>
          </Act>
        </div>

        <div className={s.col} aria-label="controls">
          <section className={s.card}>
            <h2 className={s.cardTitle}><span>Gate</span><span>{gateMode ?? "?"}</span></h2>
            <div className={s.row}>
              <div className={s.seg} role="group" aria-label="decider gate mode">
                <button className={gateMode === "enforce" ? s.segOn : ""} onClick={() => setGate("enforce")}>ENFORCE</button>
                <button className={gateMode === "advisory" ? s.segOn : ""} onClick={() => setGate("advisory")}>ADVISORY</button>
                <button className={gateMode === "off" ? s.segOn : ""} onClick={() => setGate("off")}>OFF</button>
              </div>
              <span className="muted">{GATE_HINT[gateMode ?? "enforce"]}</span>
            </div>
            {gateT && <ToastLine t={gateT} />}
          </section>

          <section className={s.card}>
            <h2 className={s.cardTitle}><span>Throttle</span><span>{throttle ?? "?"}</span></h2>
            <div className={s.row}>
              <input type="number" step="0.05" min="0.1" max="0.9" value={throttleDraft} onChange={(e) => setThrottleDraft(e.target.value)} aria-label="servo throttle for a 0.3 m/s hop" style={{ width: "6em" }} />
              <button onClick={() => void applyThrottle()}>Apply</button>
              <button onClick={() => void testHop()}>Test hop</button>
            </div>
            <span className="muted">servo throttle for a hop at the 0.3 m/s cap; free wheels spin at 0.3, the floor needs about 0.5 (the stock console sends 0.55). Saved to ~/.config/deepracer/calibration.json.</span>
            {thrT && <ToastLine t={thrT} />}
          </section>

          <section className={s.card}>
            <h2 className={s.cardTitle}><span>Body</span><span>{store.state?.runtime ?? ""}</span></h2>
            <div className={s.row}>
              <div className={s.seg} role="group" aria-label="active body">
                <button className={body === "sim" ? s.segOn : ""} onClick={() => send({ op: "body", active: "sim" })}>SIM</button>
                <button className={body === "car" ? s.segOn : ""} onClick={() => send({ op: "body", active: "car" })}>CAR</button>
              </div>
              <span className="muted">{body ? (body === "car" ? "DeepRacer" : "twin / fake car") : "unknown"}</span>
            </div>
          </section>

          <section className={s.card}>
            <h2 className={s.cardTitle}><span>Approvals</span><span>{store.pending.length}</span></h2>
            {store.pending.length === 0 && <div className="hint">Approve / Deny appear here (and as a modal on the stage) when the gate asks Confirm.</div>}
            {store.pending.map((p) => (
              <div key={p.request_id} className={s.approval}>
                <div className={s.approvalText}><b>Confirm needed</b> · {p.reason ?? "outside the briefed envelope"} <span className="mono dim">{p.request_id}</span></div>
                <button className="btnGood" onClick={() => send({ op: "approve", request_id: p.request_id, approved: true })}>Approve</button>
                <button className="btnBad" onClick={() => send({ op: "approve", request_id: p.request_id, approved: false })}>Deny</button>
              </div>
            ))}
          </section>

          <section className={s.card}>
            <h2 className={s.cardTitle}><span>Stop</span><span>Esc</span></h2>
            <button className="stopAll" onClick={() => send({ op: "stop_all" })} aria-label="stop all">STOP ALL</button>
            <div className={`toast ${store.lastError ? "err" : ""}`}>{store.lastError ? `error: ${store.lastError}` : lastAck ? `ack ${String(lastAck.for)}${lastAck.request_id ? ` ${String(lastAck.request_id)}` : ""}` : ""}</div>
            <div className="hint">STOP ALL zeroes the servos and drops the heartbeat; the on-car deadman and the pen do the rest.</div>
          </section>

          <section className={s.card}>
            <h2 className={s.cardTitle}><span>Voice</span><span>space</span></h2>
            <PttButton held={pttHeld} ptt={ptt} />
          </section>

          <div className={s.pf}><Preflight preflight={preflight} send={send} /></div>
        </div>

        <div className={s.col} aria-label="audit">
          <section className={s.card}>
            <h2 className={s.cardTitle}><span>Filter</span><span>{store.events.length} events</span></h2>
            <div className={s.filters}>
              <button className={filter === "all" ? s.on : ""} onClick={() => setFilter("all")}>all</button>
              {EVENT_TYPES.map((t) => <button key={t} className={filter === t ? s.on : ""} onClick={() => setFilter(t)}>{t}</button>)}
            </div>
          </section>
          <div className={s.auditWrap}><Audit events={store.events} session={session} only={only} limit={150} /></div>
        </div>
      </main>
      <footer className="footer">
        <span className="safety"><b>{SAFETY_LINE}</b> <span>The decider is the narrator, not the brake.</span></span>
        <span className="keys">space = talk · esc = stop all · 1 2 3 views</span>
      </footer>
    </>
  );
}
