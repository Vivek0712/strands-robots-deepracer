// Frame Judge kiosk: an attendee holds anything to the camera, the decider names it with a probability
// and a latency, the presenter adds labels live, and a leaderboard keeps the best fools. Frames are
// saved to the run dir only with the attendee's consent; the card says what happened to the picture.

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Panel } from "./Panel";
import { LiveView } from "./LiveView";
import k from "./Kiosk.module.css";
import { fmtTime, frameUrl } from "../ws";
import { fmtMs, fmtP, getJson, postJson, KioskError } from "../kiosk";
import type { JudgeResult, LabelInfo, LabelsPayload, LeaderboardEntry, LeaderboardPayload } from "../kiosk";
import type { PortalEvent, VerdictPayload } from "../types";

function asVerdictEvent(r: JudgeResult | null): PortalEvent<VerdictPayload> | undefined {
  if (!r) return undefined;
  return {
    ts: r.ts, seq: 0, session: r.session ?? "", beat: "kiosk-judge", type: "verdict", source: "kiosk",
    payload: { request_id: r.request_id, stage: "frame", action: r.action, reason: r.reason, class: r.class, probability: r.probability, latency_ms: r.latency_ms ?? 0, frame_ref: r.frame_ref },
  };
}

function Bars({ probs, top }: { probs: Record<string, number>; top: string | null }) {
  const rows = Object.entries(probs).sort((a, b) => b[1] - a[1]);
  if (!rows.length) return null;
  return (
    <div className={k.bars}>
      {rows.map(([name, p]) => (
        <div key={name} className={`${k.bar} ${name === top ? k.barTop : ""}`}>
          <span className={k.barName}>{name}</span>
          <span className={k.barTrack}><span className={k.barFill} style={{ width: `${Math.round(p * 100)}%` }} /></span>
          <span className={k.barP}>{p.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

export function JudgeKiosk({ session, body }: { session?: string; body: string }) {
  const [labels, setLabels] = useState<LabelInfo[]>([]);
  const [maxLabels, setMaxLabels] = useState(12);
  const [nickname, setNickname] = useState("");
  const [expected, setExpected] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<JudgeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [board, setBoard] = useState<LeaderboardEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [newLabel, setNewLabel] = useState("");
  const [labelError, setLabelError] = useState<string | null>(null);

  const refreshLabels = useCallback(async () => {
    try { const p = await getJson<LabelsPayload>("/kiosk/labels"); setLabels(p.labels); setMaxLabels(p.max); } catch { /* portal away; retry on next action */ }
  }, []);
  const refreshBoard = useCallback(async () => {
    try { const p = await getJson<LeaderboardPayload>("/kiosk/leaderboard"); setBoard(p.entries); setTotal(p.total); } catch { /* same */ }
  }, []);
  useEffect(() => { void refreshLabels(); void refreshBoard(); }, [refreshLabels, refreshBoard]);

  const judge = async (e: FormEvent) => {
    e.preventDefault();
    if (!nickname.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      const r = await postJson<JudgeResult>("/kiosk/judge", { nickname: nickname.trim(), consent, expected: expected || null });
      setResult(r);
      void refreshBoard();
    } catch (err) {
      setError(err instanceof KioskError ? `${err.message} (HTTP ${err.status})` : String(err));
    } finally { setBusy(false); }
  };

  const addLabel = async (e: FormEvent) => {
    e.preventDefault();
    const t = newLabel.trim();
    if (!t) return;
    setLabelError(null);
    try { const p = await postJson<LabelsPayload>("/kiosk/labels", { label: t }); setLabels(p.labels); setNewLabel(""); }
    catch (err) { setLabelError(err instanceof Error ? err.message : String(err)); }
  };
  const removeLabel = async (label: string) => {
    setLabelError(null);
    try { const p = await postJson<LabelsPayload>("/kiosk/labels", { label, remove: true }); setLabels(p.labels); }
    catch (err) { setLabelError(err instanceof Error ? err.message : String(err)); }
  };

  const v = result;
  return (
    <>
      <div className={k.live}><LiveView verdict={asVerdictEvent(v)} body={body} /></div>
      <div className={k.verdict}>
        <Panel title="Frame Judge" right={<span className={k.muted}>{labels.length} labels on the card</span>}>
          <form className={k.form} onSubmit={judge}>
            <label>nickname<input data-judge-nickname value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="who is fooling the decider?" maxLength={40} autoComplete="off" /></label>
            <label>I am holding
              <select data-judge-expected value={expected} onChange={(e) => setExpected(e.target.value)}>
                <option value="">(not saying)</option>
                {labels.map((l) => <option key={l.label} value={l.label}>{l.label}</option>)}
              </select>
            </label>
            <label className={`${k.consent} ${consent ? k.consentOn : ""}`}>
              <input data-judge-consent type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
              <span>Keep my frame for the booth dataset<small>{consent ? "the frame is written to the run dir on this laptop; it never leaves it" : "off: the frame is judged in memory and discarded"}</small></span>
            </label>
            <button data-judge-go type="submit" className={k.big} disabled={busy || !nickname.trim()}>{busy ? "ASKING THE DECIDER…" : "JUDGE THIS FRAME"}</button>
          </form>
          <div className={k.verdictWrap}>
            {error && <div className={k.err}>{error}</div>}
            {!v && !error && <div className={k.muted}>Hold something up to the camera, type a nickname, press Judge. The decider answers over the labels on the card; the presenter can add one live.</div>}
            {v && (
              <>
                <div className={`${k.cls} ${v.class ? k[v.action] : k.idle}`} data-judge-class>{v.class ?? "no answer"}</div>
                <div className={k.numbers}>
                  <div className={k.num}><small>probability</small>{fmtP(v.probability)}</div>
                  <div className={k.num}><small>decider latency</small>{fmtMs(v.latency_ms)}</div>
                  <div className={k.num}><small>gate would say</small><span className={k[v.action]}>{v.action}</span></div>
                </div>
                <div className={`${k.reason} ${v.wrong ? k.fool : ""}`}>{v.reason}</div>
                <div className={`${k.saved} ${v.frame_saved ? k.savedYes : k.savedNo}`} data-judge-saved>
                  {v.frame_saved ? `frame saved with consent: ${v.frame_ref}` : "frame judged in memory, not saved (no consent)"}
                </div>
                {v.error && <div className={k.err}>decider: {v.error}</div>}
                <Bars probs={v.probabilities} top={v.class} />
              </>
            )}
          </div>
        </Panel>
      </div>
      <div className={k.labels}>
        <Panel title="Label card" right={<span className={k.muted}>{labels.length} / {maxLabels} · no retraining</span>}>
          <div className={k.chips}>
            {labels.map((l) => (
              <span key={l.label} data-label-chip={l.label} className={`${k.chip} ${l.builtin ? "" : k.chipNew}`} title={l.description ?? ""}>
                {l.label}
                {labels.length > 2 && <button type="button" aria-label={`remove ${l.label}`} onClick={() => void removeLabel(l.label)}>×</button>}
              </span>
            ))}
          </div>
          <form className={k.addRow} onSubmit={addLabel}>
            <input data-label-input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="add a label live: shoe, badge, coffee cup…" maxLength={32} />
            <button data-label-add type="submit">Add</button>
          </form>
          {labelError && <div className={k.err}>{labelError}</div>}
          <div className={k.hint}>A new label is on the next question at once: the decider is asked over the new list, nothing is retrained. Built-in labels are the gate's five frame classes.</div>
        </Panel>
      </div>
      <div className={k.board}>
        <Panel title="Best fools" right={<span className={k.muted}>{total} judgements this session</span>}>
          <div className={k.scroll}>
            {board.length === 0 && <div className={k.muted}>Nobody has fooled the decider yet. A wrong class beats a low probability.</div>}
            {board.length > 0 && (
              <table className={k.table} data-leaderboard>
                <thead><tr><th>#</th><th>nickname</th><th>decider said</th><th>they said</th><th className="r">p</th><th className="r">ms</th><th>frame</th></tr></thead>
                <tbody>
                  {board.map((row) => {
                    const url = frameUrl(session, row.frame_ref);
                    return (
                      <tr key={row.nickname}>
                        <td className={k.rank}>{row.rank}</td>
                        <td>{row.nickname}<div className={k.muted} style={{ fontSize: 12 }}>{row.tries} {row.tries === 1 ? "try" : "tries"} · {fmtTime(row.ts)}</div></td>
                        <td>{row.class ?? "—"}</td>
                        <td className={row.wrong ? k.wrong : undefined}>{row.expected ?? "—"}{row.wrong ? " ✓ fooled" : ""}</td>
                        <td className="r">{fmtP(row.probability)}</td>
                        <td className="r">{row.latency_ms ?? "—"}</td>
                        <td>{url ? <img className={k.thumb} src={url} alt="consented frame" loading="lazy" /> : <span className={k.muted}>{row.consent ? "—" : "not kept"}</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </Panel>
      </div>
    </>
  );
}
