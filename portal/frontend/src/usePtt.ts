// Push-to-talk state shared by the Stage and Operator views. While `pttHeld` is true the microphone
// is captured, decimated to 16 kHz int16 and streamed as binary frames on /ws/audio (audio.ts); the
// rover's reply PCM streams back on the same socket and plays here. With browser audio off the ptt
// down/up ops still ride the main socket so the runtime sees the press (text mode).

import { useEffect, useRef, useState } from "react";
import { AudioSocket, PcmPlayer, PttCapture, audioWsUrl } from "./audio";
import type { VoiceStatus } from "./audio";
import type { ClientOp } from "./types";

export type Mic = "idle" | "on" | "unavailable";
export type Link = "connecting" | "open" | "closed" | "off";

export const VOICE_LABEL: Record<VoiceStatus["state"], string> = {
  off: "voice off (PORTAL_VOICE=0)",
  idle: "voice idle; first press connects",
  starting: "connecting to Nova Sonic",
  live: "Nova Sonic live",
  error: "voice error",
};

export interface PttState {
  mic: Mic;
  link: Link;
  voice: VoiceStatus;
  level: number;
  frames: number;
  rover: boolean;
  lastError: string | null;
  status: string;
}

const AUDIO_KEY = "pitwall.audio";

export function readAudioEnabled(): boolean {
  try { return localStorage.getItem(AUDIO_KEY) !== "0"; } catch { return true; }
}
export function writeAudioEnabled(on: boolean): void {
  try { localStorage.setItem(AUDIO_KEY, on ? "1" : "0"); } catch { /* private window */ }
}

export function usePtt(send: (op: ClientOp) => boolean, pttHeld: boolean, audioEnabled: boolean): PttState {
  const cap = useRef<PttCapture | null>(null);
  const sock = useRef<AudioSocket | null>(null);
  const player = useRef<PcmPlayer | null>(null);
  const held = useRef(false);
  const [mic, setMic] = useState<Mic>("idle");
  const [link, setLink] = useState<Link>(audioEnabled ? "connecting" : "off");
  const [voice, setVoice] = useState<VoiceStatus>({ state: "idle" });
  const [level, setLevel] = useState(0);
  const [frames, setFrames] = useState(0);
  const [rover, setRover] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    if (!audioEnabled) { setLink("off"); return; }
    player.current = new PcmPlayer(16000);
    const socket = new AudioSocket(
      audioWsUrl(),
      (m) => {
        if (m.op === "audio_ready") { player.current?.setRate(m.sample_rate); setVoice(m.voice); }
        else if (m.op === "ack" && m.voice) setVoice(m.voice);
        else if (m.op === "barge_in") { player.current?.flush(); setRover(false); }
        else if (m.op === "error") setLastError(m.reason);
      },
      (pcm) => { player.current?.play(pcm); setRover(true); },
      setLink,
    );
    sock.current = socket;
    const tick = window.setInterval(() => setRover(player.current?.speaking ?? false), 250);
    return () => { window.clearInterval(tick); socket.close(); sock.current = null; void player.current?.close(); player.current = null; };
  }, [audioEnabled]);

  useEffect(() => {
    const ptt = (state: "down" | "up") => {
      if (!sock.current?.sendOp({ op: "ptt", state })) send({ op: "ptt", state });
    };
    if (pttHeld && !held.current) {
      held.current = true;
      ptt("down");
      setLastError(null);
      if (audioEnabled) {
        cap.current = new PttCapture();
        void cap.current.start((pcm, lvl) => {
          setLevel(lvl);
          if (sock.current?.sendPcm(pcm)) setFrames((n) => n + 1);
        }).then((ok) => { setMic(ok ? "on" : "unavailable"); if (!ok) setLastError(cap.current?.lastError ?? "microphone unavailable"); });
      }
    } else if (!pttHeld && held.current) {
      held.current = false;
      void cap.current?.stop();
      cap.current = null;
      ptt("up");
      setLevel(0);
      setMic((m) => (m === "on" ? "idle" : m));
    }
  }, [pttHeld, send, audioEnabled]);

  const status =
    !audioEnabled ? "browser audio off; press still reaches the rover" :
    mic === "unavailable" ? "mic unavailable" :
    link !== "open" ? `audio link ${link}` :
    mic === "on" ? `mic live, 16 kHz, ${frames} frames` :
    VOICE_LABEL[voice.state] ?? voice.state;

  return { mic, link, voice, level, frames, rover, lastError, status };
}

/** Pointer PTT from any button reaches App through this window event, like the keyboard space bar. */
export function pttDispatch(down: boolean): void {
  window.dispatchEvent(new CustomEvent("pitwall:ptt", { detail: down }));
}
