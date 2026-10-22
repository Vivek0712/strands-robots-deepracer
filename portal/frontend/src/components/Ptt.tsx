// Hold-to-talk button plus level meter. The press rides the same window event as the space bar.
import { pttDispatch } from "../usePtt";
import type { PttState } from "../usePtt";

export function PttButton({ held, ptt, big }: { held: boolean; ptt: PttState; big?: boolean }) {
  const bars = 24;
  const lit = Math.round(Math.min(1, ptt.level * 3) * bars);
  return (
    <div>
      <button
        className={`ptt ${held ? "on" : ""}`}
        style={big ? { fontSize: 30, padding: 22 } : undefined}
        data-ptt
        onPointerDown={(e) => { e.preventDefault(); pttDispatch(true); }}
        onPointerUp={() => pttDispatch(false)}
        onPointerCancel={() => pttDispatch(false)}
        onPointerLeave={() => { if (held) pttDispatch(false); }}
        aria-pressed={held}
      >
        {held ? "LISTENING" : ptt.rover ? "ROVER SPEAKING" : "HOLD TO TALK"}
      </button>
      <div className="meter" role="meter" aria-label="microphone level" aria-valuenow={Math.round(ptt.level * 100)} aria-valuemin={0} aria-valuemax={100}>
        {Array.from({ length: bars }, (_, i) => (
          <span key={i} className={`meterBar ${i < lit ? (i > bars * 0.8 ? "meterHot" : "meterOn") : ""}`} />
        ))}
        <span className="meterTag">{held ? (ptt.mic === "on" ? "you" : "mic…") : ptt.rover ? "rover" : ptt.voice.state === "live" ? "ready" : ptt.link === "off" ? "text mode" : ""}</span>
      </div>
      <div className={`hint ${ptt.voice.state === "error" || ptt.mic === "unavailable" ? "err" : ""}`}>{ptt.lastError && ptt.voice.state !== "live" ? (ptt.voice.error ?? ptt.lastError) : ptt.status}</div>
    </div>
  );
}
