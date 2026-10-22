// The gate asked Confirm: the room sees the question and the speaker answers it on screen.
import type { ClientOp, PendingApproval } from "../types";
import { fmtTime } from "../ws";

export function ApprovalModal({ pending, send }: { pending: PendingApproval[]; send: (op: ClientOp) => boolean }) {
  if (pending.length === 0) return null;
  const p = pending[0];
  return (
    <div className="modalBack" role="dialog" aria-modal="true" aria-labelledby="approval-title">
      <div className="modal">
        <h2 id="approval-title" className="modalTitle">CONFIRM?</h2>
        <div className="modalReason">{p.reason || "The plan is outside the briefed envelope."}</div>
        <div className="modalMeta">{p.stage ? `${p.stage} stage · ` : ""}{p.request_id} · asked {fmtTime(p.ts)}{pending.length > 1 ? ` · ${pending.length - 1} more waiting` : ""}</div>
        <div className="modalRow">
          <button className="btnGood" onClick={() => send({ op: "approve", request_id: p.request_id, approved: true })}>Approve</button>
          <button className="btnBad" onClick={() => send({ op: "approve", request_id: p.request_id, approved: false })}>Deny</button>
        </div>
        <div className="hint" style={{ marginTop: 14 }}>Approving releases one hop inside the hop cap. Physics stops the car; the decider explains.</div>
      </div>
    </div>
  );
}
