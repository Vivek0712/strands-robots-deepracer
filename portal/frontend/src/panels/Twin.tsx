// Twin canvas: the 2 x 2 m pen and the kinematic twin's pose trail, drawn from `body` events whose
// payload says `body: "twin"` (CONTRACTS section 4). The views mount it only once a twin sample has
// arrived, so a car-only show never sees it. Physics stops the car; the decider explains.

import { useEffect, useMemo, useRef } from "react";
import type { PortalEvent, TwinPose } from "../types";

const PEN_M = 2.0;
const CAR_LEN_M = 0.3;
const CAR_WIDTH_M = 0.2;
const MAX_TRAIL = 400;

export function twinPose(e: PortalEvent): TwinPose | null {
  if (e.type !== "body") return null;
  const q = e.payload as Record<string, unknown>;
  if (q.body !== "twin" || typeof q.x !== "number" || typeof q.y !== "number" || typeof q.yaw !== "number") return null;
  return q as unknown as TwinPose;
}

export function useTwinTrail(events: PortalEvent[]): TwinPose[] {
  return useMemo(() => {
    const out: TwinPose[] = [];
    for (const e of events) { const q = twinPose(e); if (q) out.push(q); }
    return out.slice(-MAX_TRAIL);
  }, [events]);
}

function draw(canvas: HTMLCanvasElement, trail: TwinPose[]) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const size = Math.min(canvas.clientWidth, canvas.clientHeight) || 220;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, size, size);
  const scale = size / PEN_M; // px per metre; the pen is centred on the twin's origin
  const toPx = (x: number, y: number) => [size / 2 + x * scale, size / 2 - y * scale] as const;

  ctx.fillStyle = "#0b0d10";
  ctx.fillRect(0, 0, size, size);
  ctx.strokeStyle = "#2a2f36";
  ctx.lineWidth = 1;
  for (let m = -0.5; m <= 0.5; m += 0.5) {
    const [gx] = toPx(m, 0);
    const [, gy] = toPx(0, m);
    ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, size); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(size, gy); ctx.stroke();
  }
  ctx.strokeStyle = "#8a8f98";
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, size - 2, size - 2);

  if (trail.length === 0) return;
  ctx.strokeStyle = "#39d98a";
  ctx.lineWidth = 2;
  ctx.beginPath();
  trail.forEach((q, i) => {
    const [x, y] = toPx(q.x, q.y);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  const last = trail[trail.length - 1];
  const [cx, cy] = toPx(last.x, last.y);
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-last.yaw);
  ctx.fillStyle = last.v === 0 ? "#e8e8e8" : "#39d98a";
  ctx.fillRect(-0.05 * scale, (-CAR_WIDTH_M / 2) * scale, CAR_LEN_M * scale, CAR_WIDTH_M * scale);
  ctx.fillStyle = "#0b0d10";
  ctx.beginPath();
  ctx.moveTo((CAR_LEN_M - 0.05) * scale, 0);
  ctx.lineTo((CAR_LEN_M - 0.12) * scale, (-CAR_WIDTH_M / 3) * scale);
  ctx.lineTo((CAR_LEN_M - 0.12) * scale, (CAR_WIDTH_M / 3) * scale);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

export function TwinCanvas({ trail, className }: { trail: TwinPose[]; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    draw(canvas, trail);
    const onResize = () => draw(canvas, trail);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [trail]);
  return <canvas ref={canvasRef} className={className} aria-label="twin pose in the 2 by 2 metre pen" />;
}

export function twinSummary(trail: TwinPose[]): { last: TwinPose; travelCm: number; state: string } | null {
  if (trail.length === 0) return null;
  const last = trail[trail.length - 1];
  const travel = trail.reduce((acc, q, i) => (i === 0 ? 0 : acc + Math.hypot(q.x - trail[i - 1].x, q.y - trail[i - 1].y)), 0);
  return { last, travelCm: travel * 100, state: last.v === 0 ? "still" : `${last.v.toFixed(2)} m/s` };
}
