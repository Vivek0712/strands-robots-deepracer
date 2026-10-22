// Simon Says kiosk: an attendee types a command on the tablet, the real DeciderGate answers Proceed,
// Guide, Confirm or Deny with the reason card, the slower re-plan it would take, and the Box egress log:
// which hosts the kiosk talked to for that answer and how long each took. Nothing here drives the car.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Panel } from "./Panel";
import { LiveView } from "./LiveView";
import k from "./Kiosk.module.css";
import { fmtTime } from "../ws";
import { fmtMs, fmtP, fmtPlan, getJson, postJson, KioskError } from "../kiosk";
import type { SimonHistoryPayload, SimonResult } from "../kiosk";
import type { PortalEvent, VerdictPayload } from "../types";

const EXAMPLES = ["hop forward", "go forward fast for two seconds", "back up slowly for 1 second", "roll forward and turn left", "turn left", "what is your battery"];

function frameVerdict(r: SimonResult | null): PortalEvent<VerdictPayload> | undefined {
  const stage = r?.stages.find((s) => s.stage === "frame");
  if (!r || !stage) return undefined;
  return { ts: r.ts, seq: 0, session: "", beat: "kiosk-simon", type: "verdict", source: "kiosk", payload: stage };
}

export function Egress({ result }: { result: SimonResult | null }) {
  const rows = result?.egress ?? [];
  const total = rows.reduce((acc, e) => acc + (e.ms ?? 0), 0);
  return (
    <Panel title="Box egress log" right={<span className={k.muted}>{rows.length} outbound {rows.length === 1 ? "call" : "calls"}</span>}>
      <div className={k.egressList} data-egress>
        {rows.length === 0 && <div className={k.muted}>{result ? "No outbound call: this answer came from the parser alone." : "The calls the kiosk makes for one command appear here, with host and milliseconds."}</div>}
        {rows.map((e, i) => (
          <div key={i} className={k.egressRow}>
            <span className={k.egressWhat} title={e.what}>{e.what}</span>
            <span className={k.egressHost}>{e.host}</span>
            <span className={k.egressMs}>{e.ms == null ? "—" : `${e.ms} ms`}</span>
          </div>
        ))}
      </div>
      {rows.length > 0 && <div className={k.egressTotal}>total {total} ms on the wire · gate latency {fmtMs(result?.latency_ms)}</div>}
      <div className={k.egressNote}>{result?.egress_note ?? "Simon Says parses the text locally and asks only the decider; no model is called. The camera grab is listed when the kiosk timed it."}</div>
    </Panel>
  );
}

export function SimonKiosk({ body }: { body: string }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SimonResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<SimonResult[]>([]);

  const refresh = useCallback(async () => {
    try { const p = await getJson<SimonHistoryPayload>("/kiosk/simon"); setHistory(p.history); if (p.history[0] && !result) setResult(p.history[0]); } catch { /* portal away */ }
  }, [result]);
  useEffect(() => { void refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (e: FormEvent | null, value?: string) => {
    e?.preventDefault();
    const t = (value ?? text).trim();
    if (!t || busy) return;
    setBusy(true); setError(null);
    try {
      const r = await postJson<SimonResult>("/kiosk/simon", { text: t });
      setResult(r);
      setHistory((h) => [r, ...h].slice(0, 50));
      setText("");
    } catch (err) {
      setError(err instanceof KioskError ? `${err.message} (HTTP ${err.status})` : String(err));
    } finally { setBusy(false); }
  };

  const v = result;
  const actionClass = v?.action ? k[v.action] : k.idle;
  return (
    <>
      <div className={k.card}>
        <Panel title="Simon Says" right={<span className={k.muted}>type a command; the gate answers</span>}>
          <form className={k.cmdRow} onSubmit={(e) => void submit(e)}>
            <input data-simon-input value={text} onChange={(e) => setText(e.target.value)} placeholder="hop forward · go forward fast for two seconds · turn left" autoFocus autoComplete="off" aria-label="command" maxLength={200} />
            <button data-simon-send type="submit" disabled={busy || !text.trim()}>{busy ? "…" : "Ask"}</button>
          </form>
          <div className={k.examples}>
            {EXAMPLES.map((ex) => <button key={ex} type="button" onClick={() => void submit(null, ex)} disabled={busy}>{ex}</button>)}
          </div>
          <div className={k.verdictWrap}>
            {error && <div className={k.err}>{error}</div>}
            {!v && !error && <div className={k.muted}>Every command goes through the same two questions the car's gate asks: is it inside the briefed envelope, and what is in front of the camera right now.</div>}
            {v && (
              <>
                <div className={`${k.action} ${actionClass}`} data-simon-action>{v.action ?? "WORDS"}</div>
                <div className={k.reason} data-simon-card>{v.card}</div>
                <div className={k.numbers}>
                  <div className={k.num}><small>frame class</small>{v.class ?? "—"}</div>
                  <div className={k.num}><small>probability</small>{fmtP(v.probability)}</div>
                  <div className={k.num}><small>gate latency</small>{fmtMs(v.latency_ms)}</div>
                  {v.command && <div className={k.num}><small>asked for</small>{fmtPlan(v.command)}</div>}
                </div>
                {v.replan && <div className={k.replan} data-simon-replan><b>Slower plan the gate would take:</b> {fmtPlan(v.replan)}{v.action === "Guide" ? " (half speed, re-plan)" : " (clipped to the briefed envelope)"}</div>}
                {v.stages.length > 0 && (
                  <div className={k.stages}>
                    {v.stages.map((s) => <span key={s.stage} className={k[s.action]}>{s.stage}: {s.action} · {s.latency_ms} ms</span>)}
                  </div>
                )}
              </>
            )}
          </div>
        </Panel>
      </div>
      <div className={k.live}><LiveView verdict={frameVerdict(v)} body={body} /></div>
      <div className={k.history}>
        <Panel title="History" right={<span className={k.muted}>{history.length} this session</span>}>
          <div className={k.list} data-simon-history>
            {history.length === 0 && <div className={k.muted}>No commands yet.</div>}
            {history.map((h, i) => (
              <div key={`${h.request_id ?? "w"}-${i}`} className={`${k.row} ${k["r_" + (h.action ?? "none")]}`}>
                <span className={`${k.rowAction} ${h.action ? k[h.action] : k.idle}`}>{h.action ?? "words"}</span>
                <span className={k.rowText}>“{h.text}”</span>
                <span className={k.rowMeta}>{h.class ? `${h.class} p=${fmtP(h.probability)} · ` : ""}{h.latency_ms != null ? `${h.latency_ms} ms · ` : ""}{fmtTime(h.ts)}</span>
                <span className={k.rowReason}>{h.reason}{h.replan ? ` → ${fmtPlan(h.replan)}` : ""}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <div className={k.egress}><Egress result={v} /></div>
    </>
  );
}
