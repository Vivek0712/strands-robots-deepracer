// Push-to-talk audio for the Pit Wall: microphone -> 16 kHz mono int16 PCM frames (100 ms) over a
// binary WebSocket (/ws/audio) while the key is held; the rover's PCM comes back on the same socket
// and is played through WebAudio. The browser's native rate is 44.1 or 48 kHz, so capture is
// box-filter decimated to 16 kHz (no aliasing shimmer from linear interpolation). Physics stops the
// car; the decider explains; this file only carries the room's voice to the runtime and back.

export type AudioFrameSink = (pcm: ArrayBuffer, level: number) => void;

const TARGET_RATE = 16000;
const FRAME_SAMPLES = 1600; // 100 ms at 16 kHz
const MAX_FRAME_BYTES = 64 * 1024;

export interface VoiceStatus {
  state: "off" | "idle" | "starting" | "live" | "error";
  error?: string | null;
  pressed?: boolean;
  listeners?: number;
}

export type AudioServerMessage =
  | { op: "audio_ready"; sample_rate: number; voice: VoiceStatus; max_frame: number }
  | { op: "ack"; for: string; state?: string; voice?: VoiceStatus }
  | { op: "barge_in" }
  | { op: "error"; for?: string; reason: string }
  | { op: "pong"; ts: string };

export function audioWsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const host = location.host || "127.0.0.1:8765";
  return `${proto}://${host}/ws/audio`;
}

/** Downsample float samples at `inRate` to 16 kHz by averaging each window (box filter). */
export function downsampleTo16k(input: Float32Array, inRate: number, carry: number[]): number[] {
  const ratio = inRate / TARGET_RATE;
  const out: number[] = [];
  let pos = 0;
  const total = carry.length + input.length;
  const src = (i: number) => (i < carry.length ? carry[i] : input[i - carry.length]);
  while (pos + ratio <= total) {
    const end = pos + ratio;
    let acc = 0;
    let n = 0;
    for (let i = Math.floor(pos); i < Math.ceil(end) && i < total; i++) { acc += src(i); n++; }
    out.push(n ? acc / n : 0);
    pos = end;
  }
  const rest: number[] = [];
  for (let i = Math.floor(pos); i < total; i++) rest.push(src(i));
  carry.length = 0;
  carry.push(...rest);
  return out;
}

export function toInt16(samples: number[]): ArrayBuffer {
  const buf = new ArrayBuffer(samples.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

export function toBase64Int16(samples: number[]): string {
  const bytes = new Uint8Array(toInt16(samples));
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

export function rms(samples: number[]): number {
  if (!samples.length) return 0;
  let acc = 0;
  for (const s of samples) acc += s * s;
  return Math.min(1, Math.sqrt(acc / samples.length));
}

/** Microphone capture: getUserMedia -> ScriptProcessor -> 16 kHz int16 frames of 100 ms. */
export class PttCapture {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: ScriptProcessorNode | null = null;
  private pending: number[] = [];
  private carry: number[] = [];
  public lastError: string | null = null;

  async start(sink: AudioFrameSink): Promise<boolean> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      this.ctx = new AudioContext();
      await this.ctx.resume();
      const src = this.ctx.createMediaStreamSource(this.stream);
      const node = this.ctx.createScriptProcessor(4096, 1, 1);
      const inRate = this.ctx.sampleRate;
      node.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        this.pending.push(...downsampleTo16k(input, inRate, this.carry));
        while (this.pending.length >= FRAME_SAMPLES) {
          const chunk = this.pending.splice(0, FRAME_SAMPLES);
          sink(toInt16(chunk), rms(chunk));
        }
      };
      src.connect(node);
      node.connect(this.ctx.destination); // a ScriptProcessor only runs when connected; it outputs silence
      this.node = node;
      this.lastError = null;
      return true;
    } catch (err) {
      this.lastError = err instanceof Error ? err.message : String(err);
      await this.stop();
      return false;
    }
  }

  async stop(): Promise<void> {
    this.node?.disconnect();
    this.node = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    if (this.ctx) { try { await this.ctx.close(); } catch { /* already closed */ } }
    this.ctx = null;
    this.pending = [];
    this.carry = [];
  }
}

/** Plays the rover's int16 mono PCM as it streams in; `flush()` on a barge-in cuts it mid-word. */
export class PcmPlayer {
  private ctx: AudioContext | null = null;
  private nextAt = 0;
  private sources: AudioBufferSourceNode[] = [];
  public speaking = false;
  constructor(private rate: number = 16000) {}

  setRate(rate: number) { this.rate = rate; }

  play(pcm: ArrayBuffer) {
    if (!this.ctx) this.ctx = new AudioContext();
    const ctx = this.ctx;
    if (ctx.state === "suspended") void ctx.resume();
    const n = Math.floor(pcm.byteLength / 2);
    if (!n) return;
    const view = new DataView(pcm);
    const buf = ctx.createBuffer(1, n, this.rate);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < n; i++) ch[i] = view.getInt16(i * 2, true) / 0x8000;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);
    const start = Math.max(ctx.currentTime + 0.02, this.nextAt);
    src.start(start);
    this.nextAt = start + buf.duration;
    this.speaking = true;
    this.sources.push(src);
    src.onended = () => {
      this.sources = this.sources.filter((s) => s !== src);
      if (!this.sources.length) this.speaking = false;
    };
  }

  flush() {
    for (const s of this.sources) { try { s.stop(); } catch { /* already stopped */ } }
    this.sources = [];
    this.nextAt = 0;
    this.speaking = false;
  }

  async close() {
    this.flush();
    if (this.ctx) { try { await this.ctx.close(); } catch { /* already closed */ } }
    this.ctx = null;
  }
}

/** The binary audio socket: reconnects, sends PCM while open, hands server frames to callbacks. */
export class AudioSocket {
  private ws: WebSocket | null = null;
  private closed = false;
  private timer: number | null = null;
  private delay = 500;
  public state: "connecting" | "open" | "closed" = "connecting";
  constructor(
    private url: string,
    private onMessage: (m: AudioServerMessage) => void,
    private onPcm: (pcm: ArrayBuffer) => void,
    private onState: (s: "connecting" | "open" | "closed") => void,
  ) {
    this.connect();
  }
  private connect() {
    if (this.closed) return;
    this.set("connecting");
    const ws = new WebSocket(this.url);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => { this.delay = 500; this.set("open"); };
    ws.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) { this.onPcm(e.data); return; }
      try { this.onMessage(JSON.parse(e.data as string) as AudioServerMessage); } catch { /* ignore */ }
    };
    ws.onclose = () => { this.set("closed"); this.schedule(); };
    ws.onerror = () => { ws.close(); };
  }
  private set(s: "connecting" | "open" | "closed") { this.state = s; this.onState(s); }
  private schedule() {
    if (this.closed || this.timer !== null) return;
    this.timer = window.setTimeout(() => { this.timer = null; this.connect(); }, this.delay);
    this.delay = Math.min(this.delay * 2, 5000);
  }
  get open(): boolean { return !!this.ws && this.ws.readyState === WebSocket.OPEN; }
  sendPcm(pcm: ArrayBuffer): boolean {
    if (!this.open || pcm.byteLength > MAX_FRAME_BYTES) return false;
    this.ws!.send(pcm);
    return true;
  }
  sendOp(op: Record<string, unknown>): boolean {
    if (!this.open) return false;
    this.ws!.send(JSON.stringify(op));
    return true;
  }
  close() { this.closed = true; if (this.timer) window.clearTimeout(this.timer); this.ws?.close(); }
}
