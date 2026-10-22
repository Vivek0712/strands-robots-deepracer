// STAGE: the projector view. The audience never looks at the car, so this screen carries the show:
// the camera (frozen on the frame the gate saw when a stop happens), the rover's words, the verdict
// with its class and probability, the body chips, and millisecond stamps for every stop.
// Physics stops the car; the decider explains. Nothing here is the safety layer.

import { useEffect, useMemo, useState } from "react";
import s from "./Stage.module.css";
import type { RunStore } from "../ws";
import { fmtTime, frameUrl } from "../ws";
import { SAFETY_LINE } from "../types";
import type {
  ClientOp, FramePayload, HeartbeatPayload, LedPayload, PortalEvent, PreflightPayload, StopPayload,
  ThoughtPayload, VerdictPayload, VoicePayload,
} from "../types";
import { StatusChips } from "../components/Chips";
import { PttButton } from "../components/Ptt";
import { TwinCanvas, twinSummary, useTwinTrail } from "../panels/Twin";
import type { PttState } from "../usePtt";

const FREEZE_HOLD_MS = 20_000;
const FRAME_WINDOW_MS = 6_000;

type Caption = { key: string; ts: string; kind: "speech" | "you" | "thought" | "barge"; text: string };

function lastOf<P>(events: PortalEvent[], pred: (e: PortalEvent) => boolean): PortalEvent<P> | undefined {
  for (let i = events.length - 1; i >= 0; i--) if (pred(events[i])) return events[i] as unknown as PortalEvent<P>;
  return undefined;
}

function captionsOf(events: PortalEvent[], n: number): Caption[] {
  const out: Caption[] = [];
  for (let i = events.length - 1; i >= 0 && out.length < n; i--) {
    const e = events[i];
    if (e.type === "thought") {
      const text = (e.payload as unknown as ThoughtPayload).text ?? "";
      const m = /^\s*rover\s*:\s*(.*)$/is.exec(text);
      out.push({ key: `${e.session}-${e.seq}`, ts: e.ts, kind: m ? "speech" : "thought", text: m ? m[1] : text });
    } else if (e.type === "voice") {
      const v = e.payload as unknown as VoicePayload;
      if (v.event === "transcript" && v.text) out.push({ key: `${e.session}-${e.seq}`, ts: e.ts, kind: "you", text: v.text });
      else if (v.event === "barge_in") out.push({ key: `${e.session}-${e.seq}`, ts: e.ts, kind: "barge", text: `BARGE-IN ${v.text ? `"${v.text}" ` : ""}at ${fmtTms(v.t_ms)}` });
    }
  }
  return out.reverse();
}

// t_ms is "ms since PTT down" by contract; a value past 1e10 is an epoch stamp, shown as clock time.
export function fmtTms(t: number): string {
  return t > 1e10 ? fmtTime(new Date(t).toISOString()) : `+${t} ms`;
}

function useNow(active: boolean, every = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const t = window.setInterval(() => setNow(Date.now()), every);
    return () => window.clearInterval(t);
  }, [active, every]);
  return now;
}

export interface StageProps {
  store: RunStore;
  send: (op: ClientOp) => boolean;
  pttHeld: boolean;
  ptt: PttState;
}

export function Stage({ store, send, pttHeld, ptt }: StageProps) {
  const { events, latest } = store;
  const session = store.state?.session;
  const body = store.state?.body;
  const verdict = latest.verdict as PortalEvent<VerdictPayload> | undefined;
  const frameVerdict = useMemo(() => lastOf<VerdictPayload>(events, (e) => e.type === "verdict" && (e.payload as unknown as VerdictPayload).stage === "frame"), [events]);
  const stop = latest.stop as PortalEvent<StopPayload> | undefined;
  const heartbeat = latest.heartbeat as PortalEvent<HeartbeatPayload> | undefined;
  const led = latest.led as PortalEvent<LedPayload> | undefined;
  const preflight = latest.preflight as PortalEvent<PreflightPayload> | undefined;
  const bargeIn = useMemo(() => lastOf<VoicePayload>(events, (e) => e.type === "voice" && (e.payload as unknown as VoicePayload).event === "barge_in"), [events]);
  const captions = useMemo(() => captionsOf(events, 4), [events]);

  // Speak the rover's lines through the browser (house speakers) when the toggle is on. Nova Sonic's
  // own audio, when live, is separate; this is the instant narrator line (Blindfold, Marshal, Sign).
  const [speak, setSpeak] = useState<boolean>(() => { try { return localStorage.getItem("pitwall.speak") === "1"; } catch { return false; } });
  const [spokenKey, setSpokenKey] = useState<string | null>(null);
  useEffect(() => {
    try { localStorage.setItem("pitwall.speak", speak ? "1" : "0"); } catch { /* private window */ }
  }, [speak]);
  useEffect(() => {
    if (!speak || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const last = [...captions].reverse().find((c) => c.kind === "speech");
    if (!last || last.key === spokenKey) return;
    setSpokenKey(last.key);
    const u = new SpeechSynthesisUtterance(last.text);
    u.rate = 1.0; u.pitch = 0.9;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }, [captions, speak, spokenKey]);
  const trail = useTwinTrail(events);
  const twin = twinSummary(trail);

  // Frozen frame: after a stop, hold the frame the gate saw (the Deny verdict's frame_ref, else the
  // last `frame` event near the stop) until the next command or motion start, at most 20 s.
  const stopTs = stop ? new Date(stop.ts).getTime() : 0;
  const now = useNow(Boolean(stop) && Date.now() - stopTs < FREEZE_HOLD_MS + 1000);
  const frozen = useMemo(() => {
    if (!stop) return null;
    const after = lastOf(events, (e) => e.seq > stop.seq && (e.type === "command" || (e.type === "motion" && (e.payload as { state?: string }).state === "start")));
    if (after || now - stopTs > FREEZE_HOLD_MS) return null;
    const deny = lastOf<VerdictPayload>(events, (e) => e.type === "verdict" && (e.payload as unknown as VerdictPayload).action === "Deny" && Boolean((e.payload as unknown as VerdictPayload).frame_ref));
    if (deny && Math.abs(new Date(deny.ts).getTime() - stopTs) < FRAME_WINDOW_MS) return { ref: deny.payload.frame_ref!, ts: deny.ts };
    const frame = lastOf<FramePayload>(events, (e) => e.type === "frame" && Math.abs(new Date(e.ts).getTime() - stopTs) < FRAME_WINDOW_MS);
    return frame ? { ref: frame.payload.frame_ref, ts: frame.ts } : null;
  }, [events, stop, stopTs, now]);
  const frozenUrl = frameUrl(session, frozen?.ref);

  // MJPEG retry when the console is away.
  const [camFailed, setCamFailed] = useState(false);
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    if (!camFailed) return;
    const t = window.setTimeout(() => { setCamFailed(false); setNonce((n) => n + 1); }, 3000);
    return () => window.clearTimeout(t);
  }, [camFailed]);

  const v = verdict?.payload;
  const fv = frameVerdict?.payload;
  const stopRecent = stop ? now - stopTs < FREEZE_HOLD_MS : false;

  return (
    <>
      <main className={s.grid}>
        <section className={s.cam} aria-label="camera">
          <div className={s.camBox}>
            {frozenUrl ? (
              <img src={frozenUrl} alt="frame the gate saw at the stop" />
            ) : !camFailed ? (
              <img src={`/api/stream/mjpeg?n=${nonce}`} alt="camera" onError={() => setCamFailed(true)} />
            ) : (
              <div className={s.noCam}>Camera feed appears here<small>waiting for /api/stream/mjpeg; the last frame the gate saw is held here when the car stops</small></div>
            )}
            {frozenUrl ? (
              <div className={`${s.tag} ${s.tagFrozen}`}>Frozen · {stop?.payload.cause}<span className={s.ms}>{frozen ? fmtTime(frozen.ts) : ""}</span></div>
            ) : (
              <div className={`${s.tag} ${s.tagLive}`}><span className={s.live} />Live</div>
            )}
            <div className={`${s.tag} ${s.tagBody}`}>{body === "car" ? "car camera" : body === "sim" ? "fake console" : "camera"}</div>
            <div className={s.overlay}>
              <div className={s.ochip}><small>frame class</small>{fv?.class ?? "—"}</div>
              <div className={`${s.ochip} num`}><small>probability</small>{fv?.probability != null ? fv.probability.toFixed(2) : "—"}</div>
              {fv && <div className={`${s.ochip} ${s.ochipAction} ${fv.action}`}><small>frame verdict</small>{fv.action}</div>}
            </div>
          </div>
        </section>

        <section className={`${s.card} ${s.cap}`} aria-label="captions">
          <h2 className={s.cardTitle}><span>Rover</span><span>{ptt.rover ? "speaking" : pttHeld ? "listening" : ""}</span></h2>
          <div className={s.capList}>
            {captions.length === 0 && <div className={s.capEmpty}>What the rover says and thinks appears here, newest at the bottom. Spoken lines are large; reasoning is grey.</div>}
            {captions.map((c) => (
              <div key={c.key} className={s.line}>
                <span className={s.lineT}>{fmtTime(c.ts)}</span>
                <span className={s[c.kind]}>{c.text}</span>
              </div>
            ))}
          </div>
        </section>

        <aside className={s.side}>
          <StatusChips body={body} heartbeat={heartbeat} led={led} preflight={preflight} conn={store.conn} compact />

          <section key={verdict?.seq ?? "none"} className={`${s.card} ${s.verdictCard} ${v?.action === "Deny" ? `${s.Deny} ${s.flash}` : ""}`} aria-label="verdict">
            <h2 className={s.cardTitle}><span>Verdict</span>{v && <b>{v.stage}</b>}</h2>
            <div className={`${s.action} ${v ? v.action : "idle"}`}>{v ? v.action : "IDLE"}</div>
            <div className={s.reason}>{v ? v.reason : <span className="dim">The gate's answer to every hop appears here: Proceed, Guide, Confirm or Deny, with its class, probability and latency.</span>}</div>
            {v && (
              <div className={s.nums}>
                <div className={`${s.n} ${s.nWide}`}><small>class</small>{v.class ?? "—"}</div>
                <div className={s.n}><small>probability</small>{v.probability != null ? v.probability.toFixed(2) : "—"}</div>
                <div className={s.n}><small>latency</small>{v.latency_ms}<span className={s.unit}>ms</span></div>
              </div>
            )}
          </section>

          <section className={`${s.card} ${s.stopCard} ${stopRecent ? s.hot : ""}`} aria-label="stop stamp">
            <h2 className={s.cardTitle}><span>Stop</span>{stop && <span className="num">{fmtTime(stop.ts)}</span>}</h2>
            {!stop && <div className={s.stopEmpty}>When the car stops, the cause (deny, barge-in, deadman, operator) and the millisecond stamp land here.</div>}
            {stop && (
              <>
                <div className={s.stopRow}>
                  <div className={s.cause}><small>cause</small>{stop.payload.cause.replace("_", " ")}</div>
                  <div className={s.bigMs}>{stop.payload.latency_ms != null ? stop.payload.latency_ms : "—"}<span className={s.unit}>ms</span></div>
                </div>
                <div className={s.stopMeta}>
                  {stop.payload.cause === "barge_in" && bargeIn ? `heard ${fmtTms(bargeIn.payload.t_ms)} after the press · ` : ""}
                  {stop.payload.cause === "deadman" ? "on-car deadman: ten zero servo pairs at 20 Hz · " : ""}
                  stop to zero servo pair{stop.payload.request_id ? ` · ${stop.payload.request_id}` : ""}
                </div>
              </>
            )}
          </section>

          {twin && (
            <section className={s.card} aria-label="twin">
              <h2 className={s.cardTitle}><span>Twin</span><span className="num">{twin.state}</span></h2>
              <div className={s.twinRow}>
                <TwinCanvas trail={trail} className={s.twinCanvas} />
                <div className={s.twinMeta}>
                  <span>x {twin.last.x.toFixed(2)} m</span>
                  <span>y {twin.last.y.toFixed(2)} m</span>
                  <span>yaw {((twin.last.yaw * 180) / Math.PI).toFixed(0)} deg</span>
                  <span>{twin.travelCm.toFixed(0)} cm travelled</span>
                </div>
              </div>
            </section>
          )}

          <div className={s.controls}>
            <button className="stopAll" onClick={() => send({ op: "stop_all" })} aria-label="stop all">STOP ALL</button>
            <button className={speak ? "chip chipOn" : "chip"} onClick={() => setSpeak((v) => !v)} aria-pressed={speak} title="speak the rover's lines through this browser">
              {speak ? "SPEAKING" : "SPEAK"}
            </button>
            <PttButton held={pttHeld} ptt={ptt} />
          </div>
        </aside>
      </main>
      <footer className="footer">
        <span className="safety"><b>{SAFETY_LINE}</b> <span>Pen, hop cap, on-car deadman, marshal's thumb.</span></span>
        <span className="keys">space = talk · esc = stop all · 1 2 3 views</span>
      </footer>
    </>
  );
}
