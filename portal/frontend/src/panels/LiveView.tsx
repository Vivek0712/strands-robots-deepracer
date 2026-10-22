import { useEffect, useState } from "react";
import { Panel } from "./Panel";
import s from "./Panel.module.css";
import type { PortalEvent, VerdictPayload } from "../types";

export function LiveView({ verdict, body }: { verdict: PortalEvent<VerdictPayload> | undefined; body: string }) {
  const [failed, setFailed] = useState(false);
  const [nonce, setNonce] = useState(0);
  useEffect(() => {
    if (!failed) return;
    const t = window.setTimeout(() => { setFailed(false); setNonce((n) => n + 1); }, 3000);
    return () => window.clearTimeout(t);
  }, [failed]);
  const v = verdict?.payload;
  const cls = v?.class ?? null;
  return (
    <Panel title="Live view" right={<span className={s.muted}>{body === "car" ? "car camera" : "fake console"}</span>}>
      <div className={s.live}>
        {!failed && <img src={`/api/stream/mjpeg?n=${nonce}`} alt="camera" onError={() => setFailed(true)} />}
        {failed && <div className={s.noCam}>no camera stream<br /><small>retrying /api/stream/mjpeg</small></div>}
        <div className={s.overlay}>
          <div className={s.chip}>
            <small>frame class</small>
            {cls ?? "—"}
          </div>
          <div className={`${s.chip} ${s.prob}`}>
            <small>probability</small>
            {v?.probability != null ? v.probability.toFixed(2) : "—"}
          </div>
        </div>
      </div>
    </Panel>
  );
}
